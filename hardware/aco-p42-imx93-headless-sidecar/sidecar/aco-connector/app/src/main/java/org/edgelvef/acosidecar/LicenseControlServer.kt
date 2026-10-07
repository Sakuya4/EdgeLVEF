package org.edgelvef.acosidecar

import android.net.LocalServerSocket
import android.net.LocalSocket
import android.net.LocalSocketAddress
import java.io.DataInputStream
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

/**
 * Accepts a license through a loopback-published, non-logging control channel.
 * The byte array is erased immediately after the Aco SDK receives the value.
 */
class LicenseControlServer(
    private val onLicense: (CharArray) -> Unit,
    private val socketPath: String = "/run/aco-ipc/license.sock",
) : AutoCloseable {
    private val running = AtomicBoolean(false)
    private var endpoint: LocalSocket? = null
    private var server: LocalServerSocket? = null

    fun start() {
        if (!running.compareAndSet(false, true)) return
        thread(name = "aco-license-control", isDaemon = true) {
            val socketFile = File(socketPath)
            socketFile.delete()
            val boundSocket = LocalSocket()
            boundSocket.bind(
                LocalSocketAddress(socketPath, LocalSocketAddress.Namespace.FILESYSTEM),
            )
            endpoint = boundSocket
            LocalServerSocket(boundSocket.fileDescriptor).use { listener ->
                server = listener
                while (running.get()) {
                    val client = try {
                        listener.accept()
                    } catch (_: Exception) {
                        break
                    }
                    client.use {
                        val input = DataInputStream(it.getInputStream())
                        val length = input.readUnsignedShort()
                        if (length !in 1..MAX_LICENSE_BYTES) return@use
                        val bytes = ByteArray(length)
                        input.readFully(bytes)
                        val chars = bytes.toString(Charsets.UTF_8).toCharArray()
                        bytes.fill(0)
                        try {
                            onLicense(chars)
                        } finally {
                            chars.fill('\u0000')
                        }
                    }
                }
            }
        }
    }

    override fun close() {
        running.set(false)
        server?.close()
        endpoint?.close()
        File(socketPath).delete()
    }

    companion object {
        private const val MAX_LICENSE_BYTES = 256
    }
}
