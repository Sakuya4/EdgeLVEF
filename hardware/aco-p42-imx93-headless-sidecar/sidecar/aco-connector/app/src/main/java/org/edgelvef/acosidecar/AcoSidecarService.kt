package org.edgelvef.acosidecar

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.net.wifi.p2p.WifiP2pManager
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.aco.ultrasound.AcoProbe
import com.aco.ultrasound.AcoProbeConnectMethod
import com.aco.ultrasound.AcoProbeDiscoveredListener
import com.aco.ultrasound.AcoUltrasound

class AcoSidecarService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private val frameServer = FrameServer()
    private val licenseControl = LicenseControlServer(::acceptLicense)

    @Volatile
    private var selectedProbe: AcoProbe? = null

    @Volatile
    private var pendingLicense: CharArray? = null

    @Volatile
    private var streaming = false
    private var retryConnectAt = 0L
    private var probeReadyAt = 0L
    private var connectingSince = 0L
    private var p2pGroupFormed = false
    private var sdkReady = false
    private var serviceStopping = false
    private var sdkResetGeneration = 0
    private var diagnosticManager: WifiP2pManager? = null
    private var diagnosticChannel: WifiP2pManager.Channel? = null

    private val discoveredListener = object : AcoProbeDiscoveredListener {
        override fun onDiscovered(acoProbeList: List<AcoProbe>) {
            if (!sdkReady || serviceStopping) return
            when (acoProbeList.size) {
                0 -> state("DISCOVERING")
                1 -> {
                    // Ignore cached callbacks while the failed SDK session is
                    // being released, and never replace an attempt in flight.
                    if (SystemClock.elapsedRealtime() < retryConnectAt || selectedProbe != null) return
                    selectedProbe = acoProbeList.first()
                    probeReadyAt = SystemClock.elapsedRealtime() + PROBE_SETTLE_MS
                    observePeerMetadata(selectedProbe!!)
                    selectedProbe?.onErrorListener = { error ->
                        // Error types only: never SDK messages or credential-bearing data.
                        Log.e(TAG, "ACO_ERROR:${error.javaClass.simpleName}")
                    }
                    state("PROBE_SELECTED")
                    state("PROBE_SETTLING")
                    connectIfReady()
                }
                else -> {
                    if (!streaming) {
                        selectedProbe = null
                        probeReadyAt = 0L
                    }
                    state("MULTIPLE_PROBES_REFUSED")
                }
            }
        }
    }

    private val pollConnection = object : Runnable {
        override fun run() {
            val probe = selectedProbe
            val now = SystemClock.elapsedRealtime()
            if (connectingSince != 0L) refreshP2pProgress()
            val connectTimeout = if (p2pGroupFormed) {
                SDK_CONNECT_TIMEOUT_MS
            } else {
                PROVISION_TIMEOUT_MS
            }
            when {
                !sdkReady -> Unit
                probe == null -> ensureDiscovery()
                probe.isConnected() && !streaming -> startStreaming(probe)
                connectingSince != 0L && now - connectingSince >= connectTimeout -> {
                    // isConnecting() can remain true until the vendor SDK's much
                    // longer internal timeout. Bound the whole attempt here so a
                    // missed Wi-Fi Direct negotiation cannot cost about a minute.
                    recoverProbe(probe, "CONNECT_TIMEOUT")
                }
                probe.isDisconnected() -> {
                    if (streaming) {
                        recoverProbe(probe, "DISCONNECTED")
                    } else if (
                        connectingSince != 0L &&
                        now - connectingSince >= DISCONNECTED_GRACE_MS
                    ) {
                        recoverProbe(probe, "CONNECT_FAILED")
                    } else if (connectingSince == 0L) {
                        connectIfReady()
                    }
                }
            }
            handler.postDelayed(this, CONNECTION_POLL_MS)
        }
    }

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIFICATION_ID, createNotification())
        frameServer.start()
        licenseControl.start()

        if (!permissionsGranted()) {
            state("PERMISSIONS_REQUIRED")
            return
        }

        if (getSystemService(WifiP2pManager::class.java) == null) {
            state("WIFI_P2P_UNAVAILABLE")
            return
        }
        diagnosticManager = getSystemService(WifiP2pManager::class.java)
        diagnosticChannel = diagnosticManager?.initialize(applicationContext, mainLooper, null)

        if (!initializeSdk()) return
        ensureDiscovery()
        handler.post(pollConnection)
        state("STARTED")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        serviceStopping = true
        handler.removeCallbacksAndMessages(null)
        pendingLicense?.fill('\u0000')
        pendingLicense = null
        selectedProbe?.let { probe ->
            try {
                if (streaming && probe.isConnected()) probe.stop()
            } catch (error: RuntimeException) {
                Log.e(TAG, "ACO_STOP_ERROR:${error.javaClass.simpleName}")
            }
        }
        destroySdk()
        licenseControl.close()
        frameServer.close()
        if (android.os.Build.VERSION.SDK_INT >= 27) diagnosticChannel?.close()
        super.onDestroy()
    }

    private fun observePeerMetadata(probe: AcoProbe) {
        val manager = diagnosticManager ?: return
        val channel = diagnosticChannel ?: return
        try {
            // Public read-only metadata only. Never log addresses, SSIDs,
            // serial numbers, WPS PINs, SDK configurations or License values.
            val target = probe.getConfig().mac
            manager.requestPeers(channel) { peers ->
                val peer = peers.deviceList.firstOrNull { it.deviceAddress.equals(target, ignoreCase = true) }
                if (peer == null) {
                    Log.i(TAG, "P2P_PEER_META:matched=false")
                } else {
                    Log.i(TAG, "P2P_PEER_META:matched=true go=${peer.isGroupOwner} keypad=${peer.wpsKeypadSupported()} display=${peer.wpsDisplaySupported()} pbc=${peer.wpsPbcSupported()}")
                }
            }
        } catch (error: RuntimeException) {
            Log.e(TAG, "P2P_META_ERROR:${error.javaClass.simpleName}")
        }
    }

    private fun acceptLicense(chars: CharArray) {
        val copy = chars.copyOf()
        handler.post {
            pendingLicense?.fill('\u0000')
            pendingLicense = copy
            state("LICENSE_RECEIVED")
            connectIfReady()
        }
    }

    private fun connectIfReady() {
        val probe = selectedProbe ?: return
        val licenseChars = pendingLicense ?: return
        if (probe.isConnected() || probe.isConnecting()) return
        val now = SystemClock.elapsedRealtime()
        if (now < retryConnectAt || now < probeReadyAt) return
        connectingSince = now
        p2pGroupFormed = false

        // Do not explicitly stop discovery before connect: Android's inactive
        // state can flush the peer cache. The platform connection flow stops
        // finding peers after validating the selected peer itself.
        val license = String(licenseChars)
        try {
            state("CONNECTING")
            probe.connect(license)
        } catch (error: RuntimeException) {
            Log.e(TAG, "ACO_CONNECT_ERROR:${error.javaClass.simpleName}")
            recoverProbe(probe, "CONNECT_FAILED")
        } finally {
            // Retain only the private in-memory CharArray for reconnects;
            // wipe it on replacement/destruction. Never persist/log in Android.
        }
    }

    private fun startStreaming(probe: AcoProbe) {
        probe.onErrorListener = { error ->
            Log.e(TAG, "ACO_ERROR:${error.javaClass.simpleName}")
        }
        probe.onStreamingListener = { data -> frameServer.publish(data.bitmap) }
        try {
            probe.streaming()
            streaming = true
            probeReadyAt = 0L
            connectingSince = 0L
            p2pGroupFormed = false
            retryConnectAt = 0L
            state("STREAMING")
        } catch (error: RuntimeException) {
            Log.e(TAG, "ACO_STREAM_ERROR:${error.javaClass.simpleName}")
            recoverProbe(probe, "STREAM_START_FAILED")
        }
    }

    private fun recoverProbe(probe: AcoProbe, reason: String) {
        // Once the SDK has owned a live control session, destroy() calls the
        // vendor connector's onDestroy(), which calls disconnect() and starts
        // the same unsafe HTTP leave-control-room request. Preserve that SDK
        // instance after a physical link loss and only reset Android P2P.
        val recoverSdkInPlace = streaming || p2pGroupFormed || probe.isConnected()
        streaming = false
        frameServer.clear()
        if (selectedProbe === probe) selectedProbe = null
        probeReadyAt = 0L
        connectingSince = 0L
        p2pGroupFormed = false
        retryConnectAt = SystemClock.elapsedRealtime() + RETRY_BACKOFF_MS

        state(reason)

        if (recoverSdkInPlace) {
            state("SDK_RECOVERING")
            val generation = ++sdkResetGeneration
            resetP2pSession {
                handler.postDelayed(
                    { finishInPlaceRecovery(generation) },
                    RETRY_BACKOFF_MS,
                )
            }
            handler.postDelayed(
                { finishInPlaceRecovery(generation) },
                P2P_RESET_CALLBACK_TIMEOUT_MS,
            )
            return
        }

        // The vendor Wi-Fi Direct disconnect path first performs an HTTP
        // leave-control-room request. After a failed negotiation or physical
        // probe loss there is no route to the probe, so that request raises an
        // uncaught ENETUNREACH before the SDK reaches cancelConnect/removeGroup.
        // Clear the platform attempt first, then rebuild the official SDK
        // discovery session in this process. The License socket and its private
        // in-memory value remain intact, avoiding process/License restart delay.
        destroySdk()
        state("SDK_RESETTING")
        val generation = ++sdkResetGeneration
        resetP2pSession {
            handler.postDelayed(
                { finishSdkReset(generation) },
                RETRY_BACKOFF_MS,
            )
        }
        // Framework action callbacks are not guaranteed after a HAL fault.
        // Keep a bounded fallback without allowing the delayed callback to
        // initialize the SDK twice.
        handler.postDelayed(
            { finishSdkReset(generation) },
            P2P_RESET_CALLBACK_TIMEOUT_MS,
        )
    }

    private fun restartDiscovery() {
        if (!sdkReady || serviceStopping || selectedProbe != null) return
        try {
            if (AcoUltrasound.isDiscoveringProbes()) {
                AcoUltrasound.stopDiscoverProbes()
            }
            AcoUltrasound.startDiscoverProbes()
            state("DISCOVERING")
        } catch (error: RuntimeException) {
            Log.e(TAG, "ACO_DISCOVERY_ERROR:${error.javaClass.simpleName}")
        }
    }

    private fun refreshP2pProgress() {
        val manager = diagnosticManager ?: return
        val channel = diagnosticChannel ?: return
        try {
            manager.requestConnectionInfo(channel) { info ->
                if (connectingSince != 0L && info.groupFormed && !p2pGroupFormed) {
                    p2pGroupFormed = true
                    state("P2P_GROUP_FORMED")
                }
            }
        } catch (error: RuntimeException) {
            Log.e(TAG, "P2P_PROGRESS_ERROR:${error.javaClass.simpleName}")
        }
    }

    private fun ensureDiscovery() {
        if (!sdkReady || serviceStopping) return
        if (SystemClock.elapsedRealtime() < retryConnectAt) return
        if (!AcoUltrasound.isDiscoveringProbes()) {
            AcoUltrasound.startDiscoverProbes()
            state("DISCOVERING")
        }
    }

    private fun initializeSdk(): Boolean {
        return try {
            AcoUltrasound.initialize(application, AcoProbeConnectMethod.WIFI_DIRECT)
            AcoUltrasound.registerProbeDiscoveredListener(discoveredListener)
            sdkReady = true
            true
        } catch (error: RuntimeException) {
            sdkReady = false
            Log.e(TAG, "ACO_INIT_ERROR:${error.javaClass.simpleName}")
            state("INITIALIZE_FAILED")
            false
        }
    }

    private fun destroySdk() {
        if (!sdkReady) return
        sdkReady = false
        try {
            AcoUltrasound.unregisterProbeDiscoveredListener()
            AcoUltrasound.destroy()
        } catch (error: RuntimeException) {
            Log.e(TAG, "ACO_DESTROY_ERROR:${error.javaClass.simpleName}")
        }
    }

    private fun finishSdkReset(generation: Int) {
        if (serviceStopping || sdkReady || generation != sdkResetGeneration) return
        if (!initializeSdk()) return
        restartDiscovery()
    }

    private fun finishInPlaceRecovery(generation: Int) {
        if (serviceStopping || !sdkReady || generation != sdkResetGeneration) return
        restartDiscovery()
    }

    private fun resetP2pSession(onComplete: () -> Unit) {
        val manager = diagnosticManager
        val channel = diagnosticChannel
        if (manager == null || channel == null) {
            onComplete()
            return
        }

        fun removeGroup() {
            try {
                manager.removeGroup(channel, object : WifiP2pManager.ActionListener {
                    override fun onSuccess() = onComplete()
                    override fun onFailure(reason: Int) {
                        // Numeric framework reason only; no peer/credential data.
                        Log.i(TAG, "P2P_REMOVE_RESULT:$reason")
                        onComplete()
                    }
                })
            } catch (error: RuntimeException) {
                Log.e(TAG, "P2P_REMOVE_ERROR:${error.javaClass.simpleName}")
                onComplete()
            }
        }

        try {
            // These operations must be serialized. Issuing both together made
            // every recovery race itself and return WifiP2pManager.BUSY (2).
            manager.cancelConnect(channel, object : WifiP2pManager.ActionListener {
                override fun onSuccess() = removeGroup()
                override fun onFailure(reason: Int) {
                    Log.i(TAG, "P2P_CANCEL_RESULT:$reason")
                    removeGroup()
                }
            })
        } catch (error: RuntimeException) {
            Log.e(TAG, "P2P_CANCEL_ERROR:${error.javaClass.simpleName}")
            removeGroup()
        }
    }

    private fun permissionsGranted(): Boolean {
        val permissions = mutableListOf(
            android.Manifest.permission.ACCESS_FINE_LOCATION,
            android.Manifest.permission.ACCESS_WIFI_STATE,
            android.Manifest.permission.CHANGE_WIFI_STATE,
            android.Manifest.permission.ACCESS_NETWORK_STATE,
            android.Manifest.permission.CHANGE_NETWORK_STATE,
        )
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            permissions += android.Manifest.permission.NEARBY_WIFI_DEVICES
        }
        if (android.os.Build.VERSION.SDK_INT >= 29) {
            permissions += android.Manifest.permission.ACCESS_BACKGROUND_LOCATION
        }
        return permissions.all {
            ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
        }
    }

    private fun createNotification(): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                NOTIFICATION_CHANNEL,
                "Aco sidecar",
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
        return NotificationCompat.Builder(this, NOTIFICATION_CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setContentTitle("EdgeLVEF probe service")
            .setContentText("On-board ultrasound acquisition")
            .setOngoing(true)
            .build()
    }

    private fun state(value: String) {
        Log.i(TAG, "STATE:$value")
    }

    companion object {
        private const val TAG = "AcoSidecar"
        private const val NOTIFICATION_CHANNEL = "aco-sidecar"
        private const val NOTIFICATION_ID = 42
        private const val CONNECTION_POLL_MS = 500L
        private const val DISCONNECTED_GRACE_MS = 5_000L
        // Discovery becomes visible before a cold-starting probe has necessarily
        // finished bringing up its Wi-Fi Direct control service. The official
        // sample gets this delay from the user selecting a discovered probe;
        // the headless service must provide it explicitly.
        private const val PROBE_SETTLE_MS = 5_000L
        // A responsive P42 answers Wi-Fi Direct provisioning within seconds.
        // Fail fast only while no group exists. Once Android reports a formed
        // group, preserve the route long enough for the SDK control handshake.
        private const val PROVISION_TIMEOUT_MS = 10_000L
        private const val SDK_CONNECT_TIMEOUT_MS = 20_000L
        private const val RETRY_BACKOFF_MS = 2_000L
        private const val P2P_RESET_CALLBACK_TIMEOUT_MS = 2_500L
    }
}
