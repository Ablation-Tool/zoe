package research.zoetic.zoe;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.widget.ImageView;
import android.widget.TextView;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

final class LaptopStreamClient {
    private final AtomicBoolean running = new AtomicBoolean(false);
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final ImageView imageView;
    private final TextView status;
    private HttpURLConnection connection;

    LaptopStreamClient(ImageView imageView, TextView status) {
        this.imageView = imageView;
        this.status = status;
    }

    void start() {
        if (!running.compareAndSet(false, true)) {
            return;
        }
        status.setText("Laptop: connecting over ADB localhost…");
        executor.execute(this::readStream);
    }

    private void readStream() {
        try {
            connection = (HttpURLConnection) new URL("http://127.0.0.1:8766/stream.mjpeg").openConnection();
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(12000);
            connection.setRequestProperty("Connection", "close");
            connection.connect();
            if (connection.getResponseCode() != HttpURLConnection.HTTP_OK) {
                throw new IOException("HTTP " + connection.getResponseCode());
            }
            InputStream input = connection.getInputStream();
            while (running.get()) {
                int length = -1;
                String line;
                while ((line = readLine(input)) != null) {
                    if (line.isEmpty()) {
                        break;
                    }
                    if (line.toLowerCase(Locale.ROOT).startsWith("content-length:")) {
                        length = Integer.parseInt(line.substring(line.indexOf(':') + 1).trim());
                    }
                }
                if (line == null) {
                    throw new IOException("laptop stream closed");
                }
                if (length < 0) {
                    continue;
                }
                if (length <= 0 || length > 2 * 1024 * 1024) {
                    throw new IOException("invalid JPEG frame length " + length);
                }
                byte[] jpeg = readFully(input, length);
                Bitmap bitmap = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.length);
                if (bitmap == null) {
                    throw new IOException("invalid JPEG frame");
                }
                imageView.post(() -> {
                    imageView.setImageBitmap(bitmap);
                    status.setText("Laptop: live over ADB localhost · no frames saved");
                });
            }
        } catch (Exception error) {
            if (running.get()) {
                status.post(() -> status.setText("Laptop feed unavailable: " + error.getMessage()
                        + ". Phone cameras remain independent."));
            }
        } finally {
            running.set(false);
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private static String readLine(InputStream input) throws IOException {
        ByteArrayOutputStream line = new ByteArrayOutputStream();
        int value;
        while ((value = input.read()) != -1) {
            if (value == '\n') {
                return line.toString("UTF-8").trim();
            }
            if (value != '\r') {
                line.write(value);
            }
            if (line.size() > 512) {
                throw new IOException("MJPEG header line is too long");
            }
        }
        return null;
    }

    private static byte[] readFully(InputStream input, int length) throws IOException {
        byte[] result = new byte[length];
        int offset = 0;
        while (offset < length) {
            int count = input.read(result, offset, length - offset);
            if (count < 0) {
                throw new IOException("truncated JPEG frame");
            }
            offset += count;
        }
        return result;
    }

    void close() {
        running.set(false);
        if (connection != null) {
            connection.disconnect();
        }
        executor.shutdownNow();
        status.setText("Laptop feed stopped.");
    }
}
