package research.zoetic.zoe;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.os.Build;
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

import java.util.List;
import java.util.Locale;
import java.util.concurrent.Executor;
import java.util.function.Consumer;

final class DeviceAiController {
    private static final String AICORE_PACKAGE = "com.google.android.aicore";
    private static final String AICORE_SERVICE = "com.google.android.apps.aicore.service.AiCoreService";
    private static final String AICORE_MULTIUSER_SERVICE = "com.google.android.apps.aicore.service.multiuser.AiCoreMultiUserService";

    interface StatusListener {
        void onStatus(String status);
    }

    private final ImageDescriber describer;
    private final boolean aiCorePresent;
    private final String diagnostic;
    private final Executor executor;
    private final StatusListener listener;
    private volatile boolean ready;
    private volatile boolean closed;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable statusTimeout;

    DeviceAiController(Context context, StatusListener listener) {
        this.listener = listener;
        this.executor = ContextCompat.getMainExecutor(context);
        this.aiCorePresent = hasRealAiCoreService(context);
        this.diagnostic = runtimeDiagnostic(context);
        this.describer = aiCorePresent
                ? ImageDescription.getClient(ImageDescriberOptions.builder(context).build())
                : null;
        this.statusTimeout = () -> {
            if (!closed) {
                listener.onStatus(
                        "On-device Gemini Nano (AICore) did not respond within 10 seconds. Bundled OCR, image labels, and color math remain available.");
            }
        };
    }

    static boolean isStubVersionName(String versionName) {
        return versionName != null && versionName.toLowerCase(Locale.US).contains("stub");
    }

    static String runtimeDiagnostic(Context context) {
        if (context == null) {
            return "unavailable";
        }
        PackageManager pm = context.getPackageManager();
        if (pm == null) {
            return "package manager unavailable on " + Build.MODEL;
        }
        PackageInfo info = packageInfo(pm, AICORE_PACKAGE);
        if (info == null) {
            return "not installed on " + Build.MODEL;
        }
        if (isStubVersionName(info.versionName)) {
            return "stub only (" + info.versionName + ") on " + Build.MODEL
                    + ". bundled offline ocr, labels & color math are active instead";
        }
        if (!hasAnyAiCoreService(pm)) {
            return "AICore service not shipped on " + Build.MODEL
                    + ". bundled offline ocr, labels & color math are active instead";
        }
        String version = info.versionName == null ? "installed" : info.versionName;
        return "AICore service detected (" + version + ")";
    }

    static boolean hasRealAiCoreService(Context context) {
        if (context == null) {
            return false;
        }
        PackageManager pm = context.getPackageManager();
        if (pm == null) {
            return false;
        }
        PackageInfo info = packageInfo(pm, AICORE_PACKAGE);
        if (info == null || isStubVersionName(info.versionName)) {
            return false;
        }
        if (info.applicationInfo != null && !info.applicationInfo.enabled) {
            return false;
        }
        return hasAnyAiCoreService(pm);
    }

    private static boolean hasAnyAiCoreService(PackageManager pm) {
        return resolvesService(pm, AICORE_SERVICE) || resolvesService(pm, AICORE_MULTIUSER_SERVICE);
    }

    private static boolean resolvesService(PackageManager pm, String className) {
        Intent intent = new Intent().setClassName(AICORE_PACKAGE, className);
        List<ResolveInfo> resolved = Build.VERSION.SDK_INT >= 33
                ? pm.queryIntentServices(intent, PackageManager.ResolveInfoFlags.of(0))
                : queryLegacyServices(pm, intent);
        return resolved != null && !resolved.isEmpty();
    }

    @SuppressWarnings("deprecation")
    private static List<ResolveInfo> queryLegacyServices(PackageManager pm, Intent intent) {
        return pm.queryIntentServices(intent, 0);
    }

    private static PackageInfo packageInfo(PackageManager pm, String packageName) {
        try {
            return Build.VERSION.SDK_INT >= 33
                    ? pm.getPackageInfo(packageName, PackageManager.PackageInfoFlags.of(0))
                    : getLegacyPackageInfo(pm, packageName);
        } catch (PackageManager.NameNotFoundException ignored) {
            return null;
        }
    }

    @SuppressWarnings("deprecation")
    private static PackageInfo getLegacyPackageInfo(PackageManager pm, String packageName)
            throws PackageManager.NameNotFoundException {
        return pm.getPackageInfo(packageName, 0);
    }

    boolean isReady() {
        return ready && !closed;
    }

    private void postStatus(String message) {
        if (closed) {
            return;
        }
        if (Looper.myLooper() == Looper.getMainLooper()) {
            listener.onStatus(message);
        } else {
            handler.post(() -> {
                if (!closed) {
                    listener.onStatus(message);
                }
            });
        }
    }

    private void armStatusCheck(String message) {
        handler.removeCallbacks(statusTimeout);
        postStatus(message);
        handler.postDelayed(statusTimeout, 10_000);
    }

    private void reportError(String message) {
        handler.removeCallbacks(statusTimeout);
        postStatus(message);
    }

    void check() {
        if (closed) {
            return;
        }
        if (!aiCorePresent || describer == null) {
            reportError("On-device Gemini Nano (AICore) is not shipped on " + Build.MODEL
                    + " (" + diagnostic + "). Bundled offline OCR, image labels, and Zoe's color meter work right now.");
            return;
        }
        armStatusCheck("Checking device AI feature status…");
        Futures.addCallback(describer.checkFeatureStatus(), new FutureCallback<Integer>() {
            @Override
            public void onSuccess(Integer status) {
                if (!closed) {
                    reportStatus(status);
                }
            }

            @Override
            public void onFailure(Throwable error) {
                String safeMsg = error == null || error.getMessage() == null ? "service unavailable" : error.getMessage();
                reportError("On-device Gemini Nano (AICore) is unavailable on this device (" + safeMsg
                        + "). Bundled offline OCR, image labels, and color math remain ready.");
            }
        }, executor);
    }

    void enable() {
        if (closed) {
            return;
        }
        if (!aiCorePresent || describer == null) {
            reportError("On-device Gemini Nano (AICore) is not shipped on " + Build.MODEL
                    + " (" + diagnostic + "). Bundled offline OCR, image labels, and Zoe's color meter work right now.");
            return;
        }
        armStatusCheck("Checking device AI before enabling it…");
        Futures.addCallback(describer.checkFeatureStatus(), new FutureCallback<Integer>() {
            @Override
            public void onSuccess(Integer status) {
                if (closed) {
                    return;
                }
                if (status == FeatureStatus.DOWNLOADABLE) {
                    postStatus("Device AI model download authorized by this action…");
                    download();
                } else {
                    reportStatus(status);
                }
            }

            @Override
            public void onFailure(Throwable error) {
                String safeMsg = error == null || error.getMessage() == null ? "service unavailable" : error.getMessage();
                reportError("On-device Gemini Nano (AICore) is unavailable on this device (" + safeMsg
                        + "). Bundled offline OCR, image labels, and color math remain ready.");
            }
        }, executor);
    }

    private void reportStatus(int status) {
        handler.removeCallbacks(statusTimeout);
        ready = status == FeatureStatus.AVAILABLE;
        if (status == FeatureStatus.UNAVAILABLE) {
            postStatus("Device AI image description is unavailable on this device. OCR and labels remain available.");
        } else if (status == FeatureStatus.DOWNLOADABLE) {
            postStatus("Device AI model is downloadable. Enable it only if you want the model service to download it.");
        } else if (status == FeatureStatus.DOWNLOADING) {
            postStatus("Device AI model is downloading. No inference has been requested yet.");
        } else if (status == FeatureStatus.AVAILABLE) {
            postStatus("Device AI image description is ready. The next inspection can use it.");
            if (describer != null) {
                Futures.addCallback(describer.getBaseModelName(), new FutureCallback<String>() {
                    @Override
                    public void onSuccess(String name) {
                        postStatus("Device AI ready: " + name + ". Separate from Zoe's deterministic measurements.");
                    }

                    @Override
                    public void onFailure(Throwable error) {
                    }
                }, executor);
            }
        } else {
            postStatus("Device AI returned unknown feature status " + status + ".");
        }
    }

    private void download() {
        handler.removeCallbacks(statusTimeout);
        if (describer == null) {
            return;
        }
        describer.downloadFeature(new DownloadCallback() {
            @Override
            public void onDownloadCompleted() {
                ready = true;
                postStatus("Device AI model downloaded and ready. No inference has run yet.");
            }

            @Override
            public void onDownloadFailed(GenAiException error) {
                ready = false;
                postStatus("Device AI download failed with code " + error.getErrorCode() + ": " + error.getMessage());
            }

            @Override
            public void onDownloadProgress(long totalBytesDownloaded) {
                postStatus("Device AI model downloaded " + totalBytesDownloaded + " bytes…");
            }

            @Override
            public void onDownloadStarted(long bytesToDownload) {
                postStatus("Device AI model download started: " + bytesToDownload + " bytes planned.");
            }
        });
    }

    /**
     * Silently checks whether the device's public AICore service already has Gemini Nano AVAILABLE
     * (never triggers an unrequested download!) so supported devices get instant on-device descriptions.
     */
    void autoPrepareQuietly() {
        if (closed || !aiCorePresent || describer == null || ready) {
            return;
        }
        Futures.addCallback(describer.checkFeatureStatus(), new FutureCallback<Integer>() {
            @Override
            public void onSuccess(Integer status) {
                if (!closed && status != null && status == FeatureStatus.AVAILABLE) {
                    ready = true;
                }
            }

            @Override
            public void onFailure(Throwable ignored) {
            }
        }, executor);
    }

    void describe(Bitmap bitmap, Consumer<String> completion) {
        if (!ready || closed || !aiCorePresent || describer == null || bitmap == null || bitmap.isRecycled()) {
            executor.execute(() -> completion.accept(null));
            return;
        }
        final java.util.concurrent.atomic.AtomicBoolean finished = new java.util.concurrent.atomic.AtomicBoolean(false);
        final Runnable guard = () -> {
            if (finished.compareAndSet(false, true)) {
                completion.accept(null);
            }
        };
        handler.postDelayed(guard, 5_000L);
        ImageDescriptionRequest request = ImageDescriptionRequest.builder(bitmap).build();
        Futures.addCallback(describer.runInference(request), new FutureCallback<ImageDescriptionResult>() {
            @Override
            public void onSuccess(ImageDescriptionResult result) {
                handler.removeCallbacks(guard);
                if (finished.compareAndSet(false, true)) {
                    completion.accept(closed || result == null ? null : result.getDescription());
                }
            }

            @Override
            public void onFailure(Throwable error) {
                handler.removeCallbacks(guard);
                if (finished.compareAndSet(false, true)) {
                    reportError("Device AI inference failed: " + (error == null ? "unknown" : error.getMessage()));
                    completion.accept(null);
                }
            }
        }, executor);
    }

    void close() {
        closed = true;
        handler.removeCallbacks(statusTimeout);
        if (describer != null) {
            describer.close();
        }
    }
}
