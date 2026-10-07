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
    private var nextConnectAt = 0L
    private var connectingSince = 0L
    private var diagnosticManager: WifiP2pManager? = null
    private var diagnosticChannel: WifiP2pManager.Channel? = null

    private val discoveredListener = object : AcoProbeDiscoveredListener {
        override fun onDiscovered(acoProbeList: List<AcoProbe>) {
            when (acoProbeList.size) {
                0 -> state("DISCOVERING")
                1 -> {
                    selectedProbe = acoProbeList.first()
                    observePeerMetadata(selectedProbe!!)
                    selectedProbe?.onErrorListener = { error ->
                        // Error types only: never SDK messages or credential-bearing data.
                        Log.e(TAG, "ACO_ERROR:${error.javaClass.simpleName}")
                    }
                    state("PROBE_SELECTED")
                    connectIfReady()
                }
                else -> {
                    if (!streaming) selectedProbe = null
                    state("MULTIPLE_PROBES_REFUSED")
                }
            }
        }
    }

    private val pollConnection = object : Runnable {
        override fun run() {
            val probe = selectedProbe
            when {
                probe == null -> ensureDiscovery()
                probe.isConnected() && !streaming -> startStreaming(probe)
                probe.isDisconnected() -> {
                    if (streaming) {
                        streaming = false
                        frameServer.clear()
                        selectedProbe = null
                        connectingSince = 0L
                        state("DISCONNECTED")
                        ensureDiscovery()
                    } else if (connectingSince != 0L && SystemClock.elapsedRealtime() - connectingSince > 5_000L) {
                        // A failed negotiation invalidates the peer cache. Do
                        // not reuse that AcoProbe: await a fresh discovery event.
                        selectedProbe = null
                        connectingSince = 0L
                        state("RETRY_DISCOVERY")
                        ensureDiscovery()
                    } else connectIfReady()
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

        try {
            AcoUltrasound.initialize(application, AcoProbeConnectMethod.WIFI_DIRECT)
        } catch (error: RuntimeException) {
            Log.e(TAG, "ACO_INIT_ERROR:${error.javaClass.simpleName}")
            state("INITIALIZE_FAILED")
            return
        }
        AcoUltrasound.registerProbeDiscoveredListener(discoveredListener)
        ensureDiscovery()
        handler.post(pollConnection)
        state("STARTED")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        pendingLicense?.fill('\u0000')
        pendingLicense = null
        selectedProbe?.stop()
        selectedProbe?.disconnect()
        AcoUltrasound.unregisterProbeDiscoveredListener()
        AcoUltrasound.destroy()
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
        if (SystemClock.elapsedRealtime() < nextConnectAt) return
        nextConnectAt = SystemClock.elapsedRealtime() + 30_000L
        connectingSince = SystemClock.elapsedRealtime()

        // Do not explicitly stop discovery before connect: Android's inactive
        // state can flush the peer cache. The platform connection flow stops
        // finding peers after validating the selected peer itself.
        val license = String(licenseChars)
        try {
            state("CONNECTING")
            probe.connect(license)
        } catch (error: RuntimeException) {
            Log.e(TAG, "ACO_CONNECT_ERROR:${error.javaClass.simpleName}")
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
        probe.streaming()
        streaming = true
        state("STREAMING")
    }

    private fun ensureDiscovery() {
        if (!AcoUltrasound.isDiscoveringProbes()) {
            AcoUltrasound.startDiscoverProbes()
            state("DISCOVERING")
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
    }
}
