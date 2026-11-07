package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Bitmap;
import android.os.Handler;
import android.os.Looper;

import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.mlkit.genai.common.DownloadCallback;
import com.google.mlkit.genai.common.FeatureStatus;
import com.google.mlkit.genai.common.GenAiException;
import com.google.mlkit.genai.imagedescription.ImageDescriber;
import com.google.mlkit.genai.imagedescription.ImageDescriberOptions;
import com.google.mlkit.genai.imagedescription.ImageDescription;
import com.google.mlkit.genai.imagedescription.ImageDescriptionRequest;
import com.google.mlkit.genai.imagedescription.ImageDescriptionResult;

import java.util.concurrent.Executor;
import java.util.function.Consumer;

final class DeviceAiController {
    interface StatusListener {
        void onStatus(String status);
    }

    private final ImageDescriber describer;
    private final Executor executor;
    private final StatusListener listener;
    private volatile boolean ready;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable statusTimeout;

    DeviceAiController(Context context, StatusListener listener) {
        this.listener = listener;
        this.executor = ContextCompat.getMainExecutor(context);
        this.describer = ImageDescription.getClient(ImageDescriberOptions.builder(context).build());
        this.statusTimeout = () -> listener.onStatus(
                "Device AI did not respond within 10 seconds. OCR and image labels remain available; no model was downloaded.");
    }

    boolean isReady() {
        return ready;
    }

    private void armStatusCheck(String message) {
        handler.removeCallbacks(statusTimeout);
        listener.onStatus(message);
        handler.postDelayed(statusTimeout, 10_000);
    }

    private void reportError(String message) {
        handler.removeCallbacks(statusTimeout);
        listener.onStatus(message);
    }

    void check() {
        armStatusCheck("Checking device AI feature status…");
        Futures.addCallback(describer.checkFeatureStatus(), new FutureCallback<Integer>() {
            @Override
            public void onSuccess(Integer status) {
                reportStatus(status);
            }

            @Override
            public void onFailure(Throwable error) {
                reportError("Device AI status failed: " + error.getMessage());
            }
        }, executor);
    }

    void enable() {
        armStatusCheck("Checking device AI before enabling it…");
        Futures.addCallback(describer.checkFeatureStatus(), new FutureCallback<Integer>() {
            @Override
            public void onSuccess(Integer status) {
                if (status == FeatureStatus.DOWNLOADABLE) {
                    listener.onStatus("Device AI model download authorized by this action…");
                    download();
                } else {
                    reportStatus(status);
                }
            }

            @Override
            public void onFailure(Throwable error) {
                reportError("Device AI could not be enabled: " + error.getMessage());
            }
        }, executor);
    }

    private void reportStatus(int status) {
        handler.removeCallbacks(statusTimeout);
        ready = status == FeatureStatus.AVAILABLE;
        if (status == FeatureStatus.UNAVAILABLE) {
            listener.onStatus("Device AI image description is unavailable on this device. OCR and labels remain available.");
        } else if (status == FeatureStatus.DOWNLOADABLE) {
            listener.onStatus("Device AI model is downloadable. Enable it only if you want the model service to download it.");
        } else if (status == FeatureStatus.DOWNLOADING) {
            listener.onStatus("Device AI model is downloading. No inference has been requested yet.");
        } else if (status == FeatureStatus.AVAILABLE) {
            listener.onStatus("Device AI image description is ready. The next inspection can use it.");
            Futures.addCallback(describer.getBaseModelName(), new FutureCallback<String>() {
                @Override
                public void onSuccess(String name) {
                    listener.onStatus("Device AI ready: " + name + ". Separate from Zoe's deterministic measurements.");
                }

                @Override
                public void onFailure(Throwable error) {
                }
            }, executor);
        } else {
            listener.onStatus("Device AI returned unknown feature status " + status + ".");
        }
    }

    private void download() {
        handler.removeCallbacks(statusTimeout);
        describer.downloadFeature(new DownloadCallback() {
            @Override
            public void onDownloadCompleted() {
                ready = true;
                listener.onStatus("Device AI model downloaded and ready. No inference has run yet.");
            }

            @Override
            public void onDownloadFailed(GenAiException error) {
                ready = false;
                listener.onStatus("Device AI download failed with code " + error.getErrorCode() + ": " + error.getMessage());
            }

            @Override
            public void onDownloadProgress(long totalBytesDownloaded) {
                listener.onStatus("Device AI model downloaded " + totalBytesDownloaded + " bytes…");
            }

            @Override
            public void onDownloadStarted(long bytesToDownload) {
                listener.onStatus("Device AI model download started: " + bytesToDownload + " bytes planned.");
            }
        });
    }

    void describe(Bitmap bitmap, Consumer<String> completion) {
        if (!ready) {
            executor.execute(() -> completion.accept(null));
            return;
        }
        ImageDescriptionRequest request = ImageDescriptionRequest.builder(bitmap).build();
        Futures.addCallback(describer.runInference(request), new FutureCallback<ImageDescriptionResult>() {
            @Override
            public void onSuccess(ImageDescriptionResult result) {
                completion.accept(result.getDescription());
            }

            @Override
            public void onFailure(Throwable error) {
                reportError("Device AI inference failed: " + error.getMessage());
                completion.accept(null);
            }
        }, executor);
    }

    void close() {
        handler.removeCallbacks(statusTimeout);
        describer.close();
    }
}
