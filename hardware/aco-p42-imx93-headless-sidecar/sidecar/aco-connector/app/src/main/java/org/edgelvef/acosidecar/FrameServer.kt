package org.edgelvef.acosidecar

import android.graphics.Bitmap
import android.net.LocalServerSocket
import android.net.LocalSocket
import android.net.LocalSocketAddress
import java.io.BufferedOutputStream
import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.io.File
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

/**
 * Initial proof-of-connection frame transport.
 *
 * The socket lives in a host directory bind-mounted into the Android sidecar,
 * so no TCP listener exists on either the probe or development network. JPEG
 * is deliberately temporary; the final implementation can replace it with
 * shared memory after P42 connectivity is proven.
 */
class FrameServer(private val socketPath: String = "/run/aco-ipc/frame.sock") : AutoCloseable {
    private val running = AtomicBoolean(false)
    private val frames = ArrayBlockingQueue<ByteArray>(1)
    private var endpoint: LocalSocket? = null
    private var server: LocalServerSocket? = null

    fun start() {
        if (!running.compareAndSet(false, true)) return
        thread(name = "aco-frame-server", isDaemon = true) {
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
                    try {
                        serve(client)
                    } catch (_: java.io.IOException) {
                        // A Linux reader may disconnect/restart. Keep accepting
                        // local clients; never terminate acquisition on EPIPE.
                    }
                }
            }
        }
    }

    fun publish(bitmap: Bitmap) {
        if (!running.get()) return
        val encoded = ByteArrayOutputStream()
        if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 85, encoded)) return
        val bytes = encoded.toByteArray()
        if (bytes.isEmpty() || bytes.size > MAX_FRAME_BYTES) return
        frames.poll()
        frames.offer(bytes)
    }

    private fun serve(client: LocalSocket) {
        client.use {
            val output = DataOutputStream(BufferedOutputStream(it.getOutputStream()))
            output.write("ACO-SIDECAR/1\n".toByteArray(Charsets.US_ASCII))
            output.flush()
            // Android LocalSocket.isClosed() is unsupported. Peer closure is
            // detected by write/flush IOException and handled by the accept loop.
            while (running.get()) {
                val frame = frames.poll(500, TimeUnit.MILLISECONDS) ?: continue
                output.writeInt(frame.size)
                output.write(frame)
                output.flush()
            }
        }
    }

    fun clear() { frames.clear() }

    override fun close() {
        running.set(false)
        server?.close()
        endpoint?.close()
        File(socketPath).delete()
        frames.clear()
    }

    companion object {
        private const val MAX_FRAME_BYTES = 2_000_000
    }
}
