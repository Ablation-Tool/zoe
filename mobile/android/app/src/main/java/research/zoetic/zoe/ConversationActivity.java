package research.zoetic.zoe;

import android.Manifest;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.AlarmClock;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.io.File;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe Next-Gen Chat Interface (v0.4.0-beta):
 *   - Chat-first bubble stream with user pills & Zoe GEM-anchored reply cards
 *   - Top Brain Switcher: Zoe Stem (<5ms offline) · Local LLM (MediaPipe Qwen2.5 offline) ·
 *     Lab Qwen (Workstation Eliza-GEM) · Cloud AI (Gemini / Claude / ChatGPT / Grok / Local OpenAI)
 *   - Collapsible Glass-Box Kloster A_tau(p) telemetry pill on every reply
 *   - Approval-gated multi-step phone action plans (Maps, Personal Safety, Flashlight, Timer, Alarm)
 *   - Zero-key 1-tap handoff to installed Claude, Grok, ChatGPT & Gemini apps + Multi-AI Council
 *   - Private on-device multi-thread history (`allowBackup="false"`) + Native 44.1 kHz Voice & Sing Zoe
 */
public final class ConversationActivity extends ComponentActivity {
    static final String EXTRA_INITIAL_PROMPT = "zoe_initial_prompt";
    static final String ZOE_CREST = "Zoe";
    private static final int MICROPHONE_PERMISSION = 73;

    private enum BrainMode {
        AUTO,
        STEM,
        LOCAL_LLM,
        LAB_QWEN,
        CLOUD_AI
    }

    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final ElizaGemClient studioClient = new ElizaGemClient();
    private volatile boolean workstationReachable;
    private volatile boolean workstationFrontierReady;
    private volatile String workstationModelLabel = "";
    private ZoeBrainEngine brain;
    private ZoeNativeVoice nativeVoice;
    private OnDeviceLlmEngine localLlm;

    private final List<ChatHistoryStore.ChatThread> threads = new ArrayList<>();
    private ChatHistoryStore.ChatThread currentThread;

    private BrainMode brainMode = BrainMode.AUTO;
    private boolean webSearchEnabled;
    private TextView status;
    private ScrollView chatScroll;
    private LinearLayout chatFeed;
    private EditText typedInput;
    private Button modeAutoBtn;
    private Button modeStemBtn;
    private Button modeLocalLlmBtn;
    private Button modeLabBtn;
    private Button modeCloudBtn;
    private Button webToggleBtn;
    private Button captionToggle;
    private Spinner voicePicker;
    private LinearLayout osActionBar;
    private Button osActionBtn;
    private LinearLayout extraPlanSteps;
    private LinearLayout attachmentBanner;
    private ImageView attachmentThumb;
    private TextView attachmentLabel;
    private MediaChatHelper.MediaAttachment pendingAttachment;

    private Uri pendingChatCaptureUri;

    private final ActivityResultLauncher<Uri> takeChatPhotoLauncher =
            registerForActivityResult(new ActivityResultContracts.TakePicture(), saved -> {
                Uri uri = pendingChatCaptureUri;
                pendingChatCaptureUri = null;
                if (Boolean.TRUE.equals(saved) && uri != null) {
                    attachMediaUri(uri, false);
                }
            });

    private final ActivityResultLauncher<Uri> takeChatVideoLauncher =
            registerForActivityResult(new ActivityResultContracts.CaptureVideo(), saved -> {
                Uri uri = pendingChatCaptureUri;
                pendingChatCaptureUri = null;
                if (Boolean.TRUE.equals(saved) && uri != null) {
                    attachMediaUri(uri, true);
                }
            });

    private final ActivityResultLauncher<String[]> pickPhotoLauncher =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
                if (uri != null) {
                    attachMediaUri(uri, false);
                }
            });

    private final ActivityResultLauncher<String[]> pickVideoLauncher =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
                if (uri != null) {
                    attachMediaUri(uri, true);
                }
            });

    private TextToSpeech textToSpeech;
    private SpeechRecognizer recognizer;
    private final List<Voice> voices = new ArrayList<>();
    private final List<OsToolsBridge.ActionSuggestion> pendingPlan = new ArrayList<>();

    private boolean ttsReady;
    private boolean startWhenReady;
    private boolean active;
    private boolean captionMode;
    private boolean useNativeVoice;
    private boolean talkTorchOn;
    private int selectedVoiceIndex;
    private String lastResponse = "hi, i'm zoe. what would you like to explore?";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        brain = new ZoeBrainEngine(this);
        nativeVoice = new ZoeNativeVoice();
        localLlm = new OnDeviceLlmEngine(this);
        executor.execute(() -> {
            MediaChatHelper.warmUp();
            File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
            if (localModel != null) {
                localLlm.warmUp(localModel);
            }
        });

        threads.addAll(ChatHistoryStore.load(this));
        if (threads.isEmpty()) {
            currentThread = ChatHistoryStore.newThread();
            threads.add(0, currentThread);
        } else {
            currentThread = threads.get(0);
        }

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        // 1. Single Clean Borderless Top Bar ([←] zoe          [+] [clear] [☰] [⚙])
        LinearLayout headerWrap = Ui.vertical(this);
        headerWrap.setBackgroundColor(Color.TRANSPARENT);
        headerWrap.setPadding(Ui.dp(this, 12), Ui.dp(this, 6), Ui.dp(this, 12), Ui.dp(this, 2));

        LinearLayout topRow = new LinearLayout(this);
        topRow.setOrientation(LinearLayout.HORIZONTAL);
        topRow.setGravity(Gravity.CENTER_VERTICAL);
        topRow.setBackgroundColor(Color.TRANSPARENT);

        Button backBtn = Ui.tonalIconButton(this, "←", "Back to Zoe home", view -> finish());
        topRow.addView(backBtn, new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 44)));

        TextView chatTitle = Ui.text(this, "Zoe", 20f, Ui.TEXT);
        chatTitle.setTypeface(Ui.SANS_MEDIUM);
        chatTitle.setLetterSpacing(-0.015f);
        chatTitle.setPadding(Ui.dp(this, 8), 0, Ui.dp(this, 4), 0);
        topRow.addView(chatTitle, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));

        Button newChatBtn = Ui.tonalIconButton(this, "+", "Start new chat", v -> startNewThread());
        newChatBtn.setId(R.id.conversation_new_chat_btn);
        topRow.addView(newChatBtn, new LinearLayout.LayoutParams(Ui.dp(this, 40), Ui.dp(this, 40)));

        Button clearBtn = modeChip("Clear", v -> clearCurrentOrAllChats());
        clearBtn.setId(R.id.conversation_clear_btn);
        clearBtn.setContentDescription("Clear current chat");
        LinearLayout.LayoutParams clrLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
        clrLp.setMargins(Ui.dp(this, 4), 0, Ui.dp(this, 4), 0);
        topRow.addView(clearBtn, clrLp);

        Button threadsBtn = Ui.tonalIconButton(this, "☰", "Saved conversations", v -> showThreadsSheet());
        threadsBtn.setId(R.id.conversation_threads_btn);
        topRow.addView(threadsBtn, new LinearLayout.LayoutParams(Ui.dp(this, 40), Ui.dp(this, 40)));

        Button brainSettingsBtn = Ui.tonalIconButton(this, "⚙", "Settings", v -> showBrainCouncilSheet());
        brainSettingsBtn.setId(R.id.conversation_brain_settings);
        topRow.addView(brainSettingsBtn, new LinearLayout.LayoutParams(Ui.dp(this, 40), Ui.dp(this, 40)));
        headerWrap.addView(topRow);

        // Whisper-quiet single-line status (zero top selector clutter - all brain/voice/web controls live in settings)
        status = Ui.text(this, "Ready", 11.5f, Ui.MUTED);
        status.setId(R.id.conversation_status);
        status.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), Ui.dp(this, 2));
        headerWrap.addView(status);
        root.addView(headerWrap);

        // 2. Center Living Chat-Bubble Feed (responsive side rails for Pixel Fold / Tablet / Desktop)
        chatScroll = new ScrollView(this);
        chatScroll.setFillViewport(true);
        chatScroll.setBackgroundColor(Color.TRANSPARENT);
        LinearLayout scrollContent = Ui.vertical(this);
        scrollContent.setBackgroundColor(Color.TRANSPARENT);
        int swDp = getResources().getConfiguration().screenWidthDp;
        int hPadDp = swDp >= 720 ? Math.min(108, (swDp - 680) / 2) : (swDp >= 600 ? 32 : 16);
        scrollContent.setPadding(Ui.dp(this, hPadDp), Ui.dp(this, 6), Ui.dp(this, hPadDp), Ui.dp(this, 12));

        chatFeed = Ui.vertical(this);
        chatFeed.setId(R.id.conversation_chat_feed);
        chatFeed.setBackgroundColor(Color.TRANSPARENT);
        scrollContent.addView(chatFeed);

        // Approval-Gated Multi-Step Action Plan Card (Meta Muse pattern x Zoe Constitution)
        osActionBar = Ui.vertical(this);
        osActionBar.setId(R.id.conversation_action_bar);
        osActionBar.setBackground(Ui.cardBackground(this, 22));
        osActionBar.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
        osActionBar.setVisibility(View.GONE);
        osActionBar.addView(Ui.text(this, "Suggested Action · Tap to Run", 12.5f, Ui.COBALT));
        osActionBtn = Ui.primaryButton(this, "Open Tool", Ui.COBALT, view -> {
            if (!pendingPlan.isEmpty()) {
                executeAction(pendingPlan.get(0));
            }
        });
        osActionBtn.setId(R.id.conversation_action_btn);
        Button dismissActionBtn = Ui.button(this, "Dismiss", Ui.MUTED, view -> clearPendingPlan());
        osActionBar.addView(Ui.buttonRow(this, osActionBtn, dismissActionBtn));
        extraPlanSteps = Ui.vertical(this);
        extraPlanSteps.setBackgroundColor(Color.TRANSPARENT);
        osActionBar.addView(extraPlanSteps);
        LinearLayout.LayoutParams actLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        actLp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 4));
        scrollContent.addView(osActionBar, actLp);

        chatScroll.addView(scrollContent);
        root.addView(chatScroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f));

        // 3. Thumb-Zone Next-Gen Composer Dock (strict 16dp horizontal rails matching Home, Explore & Vision!)
        LinearLayout bottomDock = Ui.vertical(this);
        bottomDock.setBackgroundColor(Color.TRANSPARENT);
        bottomDock.setPadding(Ui.dp(this, 16), Ui.dp(this, 6), Ui.dp(this, 16), Ui.dp(this, 12));

        // Dismissible Photo / Video Attachment Preview Banner
        attachmentBanner = new LinearLayout(this);
        attachmentBanner.setOrientation(LinearLayout.HORIZONTAL);
        attachmentBanner.setGravity(Gravity.CENTER_VERTICAL);
        attachmentBanner.setBackground(Ui.cardBackground(this, 18));
        attachmentBanner.setPadding(Ui.dp(this, 10), Ui.dp(this, 6), Ui.dp(this, 10), Ui.dp(this, 6));
        attachmentBanner.setVisibility(View.GONE);
        attachmentThumb = new ImageView(this);
        attachmentThumb.setScaleType(ImageView.ScaleType.CENTER_CROP);
        attachmentBanner.addView(attachmentThumb, new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 44)));
        attachmentLabel = Ui.text(this, "", 12.5f, Ui.TEXT);
        attachmentLabel.setPadding(Ui.dp(this, 10), 0, Ui.dp(this, 8), 0);
        attachmentBanner.addView(attachmentLabel, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button clearAttBtn = Ui.button(this, "✕", Ui.MUTED, v -> clearAttachment());
        attachmentBanner.addView(clearAttBtn, new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 40)));
        LinearLayout.LayoutParams attLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        attLp.setMargins(0, 0, 0, Ui.dp(this, 6));
        bottomDock.addView(attachmentBanner, attLp);

        LinearLayout composer = new LinearLayout(this);
        composer.setOrientation(LinearLayout.HORIZONTAL);
        composer.setGravity(Gravity.CENTER_VERTICAL);
        composer.setBackground(Ui.cardBackground(this, 30));
        composer.setElevation(Ui.dp(this, 5));
        composer.setPadding(Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4));

        ImageView attachBtn = Ui.iconActionButton(this, R.drawable.ic_zoe_plus, Ui.textColor(this),
                Color.TRANSPARENT, "Attach photo, video, or open guided vision or zoe explore",
                v -> showAttachAndCreateSheet());
        attachBtn.setId(R.id.conversation_attach_btn);
        composer.addView(attachBtn, new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 44)));

        typedInput = Ui.input(this, "", "Ask Zoe...");
        typedInput.setId(R.id.conversation_input);
        typedInput.setBackgroundColor(Color.TRANSPARENT);
        typedInput.setPadding(Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10));
        typedInput.setMaxLines(4);
        typedInput.setImeOptions(EditorInfo.IME_ACTION_SEND);
        typedInput.setOnEditorActionListener((v, actionId, ev) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND
                    || (ev != null && ev.getKeyCode() == KeyEvent.KEYCODE_ENTER
                    && ev.getAction() == KeyEvent.ACTION_DOWN && !ev.isShiftPressed())) {
                sendTypedMessage();
                return true;
            }
            return false;
        });
        composer.addView(typedInput, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));

        Button send = Ui.primaryButton(this, "Send", Ui.CYAN, view -> sendTypedMessage());
        send.setId(R.id.conversation_send);
        send.setMinHeight(Ui.dp(this, 44));
        send.setMinimumHeight(Ui.dp(this, 44));
        composer.addView(send, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout.LayoutParams compLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        compLp.setMargins(0, 0, 0, Ui.dp(this, 6));
        bottomDock.addView(composer, compLp);

        Button start = Ui.primaryButton(this, "Talk", Ui.COBALT, view -> startConversation());
        start.setId(R.id.conversation_start);
        start.setTextSize(13f);
        start.setMinHeight(Ui.dp(this, 38));
        start.setMinimumHeight(Ui.dp(this, 38));
        Button stop = Ui.button(this, "Stop", Ui.RUBY, view -> stopConversation());
        stop.setId(R.id.conversation_stop);
        stop.setTextSize(13f);
        stop.setMinHeight(Ui.dp(this, 38));
        stop.setMinimumHeight(Ui.dp(this, 38));
        bottomDock.addView(Ui.buttonRow(this, start, stop));
        root.addView(bottomDock);

        setContentView(Ui.wrapWithBackdrop(this, root));
        Ui.configureEdgeToEdge(this, root);

        styleBrainModeStrip();
        renderChatFeed();
        probeWorkstationBridgeAsync();

        String initialPrompt = getIntent() == null ? null : getIntent().getStringExtra(EXTRA_INITIAL_PROMPT);
        if (initialPrompt != null && !initialPrompt.trim().isEmpty()) {
            String cleanPrompt = initialPrompt.trim();
            chatScroll.post(() -> {
                if (!isFinishing() && !isDestroyed()) {
                    processUserPrompt(cleanPrompt, false);
                }
            });
        }

        textToSpeech = new TextToSpeech(this, result -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) {
                return;
            }
            ttsReady = result == TextToSpeech.SUCCESS;
            if (ttsReady && textToSpeech != null) {
                textToSpeech.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override public void onStart(String utteranceId) { }

                    @Override
                    public void onDone(String utteranceId) {
                        runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed() && active && "zoe-turn".equals(utteranceId)) {
                                startListening();
                            }
                        });
                    }

                    @Override
                    public void onError(String utteranceId) {
                        runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed() && active && "zoe-turn".equals(utteranceId)) {
                                startListening();
                            }
                        });
                    }
                });
                loadVoices();
                if (startWhenReady) {
                    startWhenReady = false;
                    speakThenListen(lastResponse);
                }
            }
        }));
    }

    private Button modeChip(String label, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(12.5f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setMaxLines(1);
        b.setMinHeight(Ui.dp(this, 34));
        b.setMinimumHeight(Ui.dp(this, 34));
        b.setPadding(Ui.dp(this, 13), 0, Ui.dp(this, 13), 0);
        b.setTextColor(Ui.mutedColor(this));
        b.setBackground(Ui.tonalPillDrawable(this, Ui.panelColor(this), Ui.primaryAccent(this), 17));
        b.setStateListAnimator(null);
        b.setOnClickListener(Ui.withHaptic(listener));
        return b;
    }

    private void toggleWebSearch() {
        webSearchEnabled = !webSearchEnabled;
        styleBrainModeStrip();
        status.setText(webSearchEnabled
                ? "live web on (https-only)"
                : "live web off (offline mode)");
    }

    private void probeWorkstationBridgeAsync() {
        String endpoint = ElizaGemClient.savedEndpoint(this);
        executor.execute(() -> {
            try {
                ElizaGemClient.Status st = studioClient.fetchStatusQuick(endpoint);
                workstationReachable = true;
                workstationFrontierReady = st.frontierReady;
                workstationModelLabel = st.frontierReady && !st.frontierModel.isEmpty()
                        ? st.frontierModel
                        : (st.localLlmReady ? st.localLlmLabel : st.defaultGear);
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) {
                        return;
                    }
                    styleBrainModeStrip();
                    if (brainMode == BrainMode.AUTO) {
                        status.setText(workstationFrontierReady
                                ? "Pro Linked (" + workstationModelLabel + ")"
                                : "Lab Linked (" + workstationModelLabel + ")");
                    }
                });
            } catch (Exception ignored) {
                workstationReachable = false;
                workstationFrontierReady = false;
                workstationModelLabel = "";
            }
        });
    }

    private void selectBrainMode(BrainMode next) {
        brainMode = next;
        styleBrainModeStrip();
        switch (next) {
            case AUTO -> {
                MultiAiClient.Provider p = MultiAiClient.activeProvider(this);
                boolean hasCloudKey = !MultiAiClient.savedKey(this, p).isEmpty();
                File model = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
                if (hasCloudKey) {
                    status.setText("Auto · " + p.displayName
                            + (webSearchEnabled ? " + Web" : ""));
                } else if (workstationReachable) {
                    status.setText(workstationFrontierReady
                            ? "Auto · Pro Linked"
                            : "Auto · Lab Linked");
                } else if (model != null) {
                    status.setText("Auto · " + OnDeviceLlmEngine.modelLabelForFile(model)
                            + (webSearchEnabled ? " + Web" : " (Offline)"));
                } else {
                    status.setText("Auto · Offline" + (webSearchEnabled ? " + Web" : ""));
                }
            }
            case STEM -> status.setText("Stem Active" + (webSearchEnabled ? " + Web" : " · Offline"));
            case LOCAL_LLM -> {
                File model = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
                if (model != null) {
                    status.setText("Local Model Ready (" + OnDeviceLlmEngine.modelLabelForFile(model) + ")");
                } else {
                    status.setText("No local model downloaded yet · Download one in Settings");
                }
            }
            case LAB_QWEN -> status.setText("Workstation Lab Mode");
            case CLOUD_AI -> {
                MultiAiClient.Provider p = MultiAiClient.activeProvider(this);
                String key = MultiAiClient.savedKey(this, p);
                if (p != MultiAiClient.Provider.LOCAL_OPENAI && key.isEmpty()) {
                    status.setText("No " + p.displayName + " key saved yet");
                } else {
                    status.setText("Online Streaming Ready (" + p.displayName + ")");
                }
            }
        }
    }

    private void styleBrainModeStrip() {
        if (modeCloudBtn != null) {
            MultiAiClient.Provider activeCloud = MultiAiClient.activeProvider(this);
            modeCloudBtn.setText(activeCloud == MultiAiClient.Provider.LOCAL_OPENAI
                    ? "local api" : shortProviderName(activeCloud));
        }
        if (modeLabBtn != null) {
            modeLabBtn.setText(workstationFrontierReady ? "pro lab" : (workstationReachable ? "lab ●" : "lab"));
        }
        if (webToggleBtn != null) {
            webToggleBtn.setText(webSearchEnabled ? "Web: On" : "Web: Off");
        }
        if (modeAutoBtn != null) styleChip(modeAutoBtn, brainMode == BrainMode.AUTO);
        if (modeStemBtn != null) styleChip(modeStemBtn, brainMode == BrainMode.STEM);
        if (modeLocalLlmBtn != null) styleChip(modeLocalLlmBtn, brainMode == BrainMode.LOCAL_LLM);
        if (modeLabBtn != null) styleChip(modeLabBtn, brainMode == BrainMode.LAB_QWEN);
        if (modeCloudBtn != null) styleChip(modeCloudBtn, brainMode == BrainMode.CLOUD_AI);
        if (webToggleBtn != null) styleChip(webToggleBtn, webSearchEnabled);
    }

    private static String shortProviderName(MultiAiClient.Provider p) {
        return switch (p) {
            case GEMINI -> "gemini";
            case CLAUDE -> "claude";
            case CHATGPT -> "chatgpt";
            case GROK -> "grok";
            case LOCAL_OPENAI -> "local api";
        };
    }

    private void styleChip(Button btn, boolean selected) {
        if (selected) {
            btn.setTextColor(Ui.isDark(this) ? Color.rgb(14, 15, 18) : Color.WHITE);
            btn.setBackground(Ui.tonalPillDrawable(this, Ui.primaryAccent(this), Ui.primaryAccent(this), 17));
        } else {
            btn.setTextColor(Ui.mutedColor(this));
            btn.setBackground(Ui.tonalPillDrawable(this, Ui.panelColor(this), Ui.primaryAccent(this), 17));
        }
    }

    private void renderChatFeed() {
        chatFeed.removeAllViews();
        if (currentThread.messages.isEmpty()) {
            chatFeed.addView(buildWelcomeCanvas());
            return;
        }
        for (int i = 0; i < currentThread.messages.size(); i++) {
            View msgView = buildMessageView(currentThread.messages.get(i));
            chatFeed.addView(msgView);
            if (i == currentThread.messages.size() - 1 && !Ui.isComfortMotionReduced()) {
                msgView.setAlpha(0f);
                msgView.setTranslationY(Ui.dp(this, 10));
                msgView.animate().alpha(1f).translationY(0f).setDuration(180L)
                        .setInterpolator(new android.view.animation.DecelerateInterpolator()).start();
            }
        }
        scrollChatToBottom();
    }

    private View buildWelcomeCanvas() {
        LinearLayout card = Ui.vertical(this);
        card.setBackgroundColor(Color.TRANSPARENT);
        card.setGravity(Gravity.CENTER_HORIZONTAL);
        card.setPadding(Ui.dp(this, 12), Ui.dp(this, 22), Ui.dp(this, 12), Ui.dp(this, 16));

        ImageView gem = Ui.gemHomeButton(this, 56, () -> Ui.goHome(this));
        gem.setId(R.id.zoe_gem_home);
        card.addView(gem, new LinearLayout.LayoutParams(Ui.dp(this, 62), Ui.dp(this, 62)));

        TextView hi = Ui.text(this, "Hi, I'm Zoe", 28f, Ui.TEXT);
        hi.setTypeface(Ui.SANS_MEDIUM);
        hi.setGravity(Gravity.CENTER);
        hi.setContentDescription("Hi, I'm Zoe");
        hi.setPadding(0, Ui.dp(this, 10), 0, Ui.dp(this, 18));
        Ui.applyGeminiGreetingShader(hi);
        card.addView(hi);

        boolean dark = Ui.isDark(this);
        int chipFill = dark ? Color.argb(210, 30, 34, 44) : Color.rgb(240, 244, 249);
        int chipStroke = dark ? Color.argb(90, 92, 112, 152) : Color.argb(145, 206, 216, 232);
        String[] starters = {
                "What does Broca's Area (BA 44) do?",
                "Where is the Hippocampus and how does memory work?",
                "Explain Cranial Nerve X (Vagus)",
                "How do you keep chats private?"
        };
        for (String starter : starters) {
            Button chip = new Button(this);
            chip.setText(starter);
            chip.setTextSize(14.5f);
            chip.setTypeface(Ui.SANS_REGULAR);
            chip.setAllCaps(false);
            chip.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            chip.setMinHeight(Ui.dp(this, 48));
            chip.setMinimumHeight(Ui.dp(this, 48));
            chip.setPadding(Ui.dp(this, 18), Ui.dp(this, 10), Ui.dp(this, 18), Ui.dp(this, 10));
            chip.setTextColor(Ui.textColor(this));
            chip.setBackground(Ui.outlinedPillDrawable(this, chipFill, chipStroke, Ui.primaryAccent(this), 22));
            chip.setStateListAnimator(null);
            Ui.attachPressSpring(chip);
            chip.setOnClickListener(Ui.withHaptic(v -> {
                typedInput.setText(starter);
                sendTypedMessage();
            }));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 4));
            card.addView(chip, lp);
        }
        return card;
    }

    private View buildMessageView(ChatHistoryStore.ChatMessage msg) {
        if ("user".equals(msg.role)) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.END);
            LinearLayout.LayoutParams rowLp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            rowLp.setMargins(Ui.dp(this, 44), Ui.dp(this, 6), 0, Ui.dp(this, 6));
            row.setLayoutParams(rowLp);

            TextView bubble = Ui.text(this, msg.text, 15.5f, Ui.TEXT);
            bubble.setTextIsSelectable(true);
            int fill = Ui.isDark(this) ? Color.rgb(32, 46, 78) : Color.rgb(219, 234, 254);
            GradientDrawable bg = new GradientDrawable();
            bg.setColor(fill);
            bg.setCornerRadius(Ui.dp(this, 22));
            bubble.setBackground(bg);
            bubble.setPadding(Ui.dp(this, 16), Ui.dp(this, 12), Ui.dp(this, 16), Ui.dp(this, 12));
            row.addView(bubble);
            return row;
        }

        // Zoe Rich Reply Card
        LinearLayout card = Ui.vertical(this);
        card.setBackground(Ui.cardBackground(this, 22));
        card.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 12));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, Ui.dp(this, 4), Ui.dp(this, 12), Ui.dp(this, 8));
        card.setLayoutParams(lp);

        LinearLayout hdr = new LinearLayout(this);
        hdr.setOrientation(LinearLayout.HORIZONTAL);
        hdr.setGravity(Gravity.CENTER_VERTICAL);
        hdr.addView(Ui.zoeSparkIcon(this, 22), new LinearLayout.LayoutParams(Ui.dp(this, 24), Ui.dp(this, 24)));

        TextView crestTxt = Ui.text(this, ZOE_CREST, 12f, Ui.COBALT);
        crestTxt.setTypeface(Ui.SANS_MEDIUM);
        crestTxt.setPadding(Ui.dp(this, 8), 0, Ui.dp(this, 6), 0);
        hdr.addView(crestTxt);

        String meta = msg.provider.isEmpty() ? "" : msg.provider;
        if (msg.latencyMs > 0) {
            meta = meta.isEmpty() ? (msg.latencyMs + " ms") : (meta + " · " + msg.latencyMs + " ms");
        }
        if (!meta.isEmpty()) {
            TextView metaTxt = Ui.text(this, meta, 11f, Ui.MUTED);
            metaTxt.setGravity(Gravity.END);
            metaTxt.setMaxLines(1);
            metaTxt.setEllipsize(android.text.TextUtils.TruncateAt.END);
            metaTxt.setPadding(Ui.dp(this, 4), 0, 0, 0);
            hdr.addView(metaTxt, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));
        }
        card.addView(hdr);

        TextView body = Ui.text(this, "", 15.5f, Ui.TEXT);
        body.setText(Ui.formatRichText(this, msg.text));
        body.setLineSpacing(0f, 1.34f);
        body.setTextIsSelectable(true);
        body.setPadding(0, Ui.dp(this, 8), 0, Ui.dp(this, 10));
        card.addView(body);

        // Clickable Verified Web Source Chips (when Live Web Grounding was used)
        if (!msg.sources.isEmpty()) {
            HorizontalScrollView srcScroll = new HorizontalScrollView(this);
            srcScroll.setHorizontalScrollBarEnabled(false);
            LinearLayout srcRow = new LinearLayout(this);
            srcRow.setOrientation(LinearLayout.HORIZONTAL);
            srcRow.setPadding(0, Ui.dp(this, 2), 0, Ui.dp(this, 6));
            for (String entry : msg.sources) {
                int bar = entry.indexOf('|');
                if (bar <= 0 || bar >= entry.length() - 1) {
                    continue;
                }
                String label = entry.substring(0, bar);
                String url = entry.substring(bar + 1);
                if (!WebSearchClient.isSafeWebUrl(url)) {
                    continue;
                }
                TextView srcChip = Ui.text(this, "🔗 " + label + " ↗", 12f, Ui.CYAN);
                srcChip.setPadding(Ui.dp(this, 10), Ui.dp(this, 6), Ui.dp(this, 10), Ui.dp(this, 6));
                srcChip.setBackground(Ui.tonalPillDrawable(this, Ui.tonalWellColor(this), Ui.CYAN, 14));
                srcChip.setClickable(true);
                srcChip.setFocusable(true);
                srcChip.setOnClickListener(v -> {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                    } catch (ActivityNotFoundException ignored) {
                        status.setText("No browser found to open " + url);
                    }
                });
                LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                slp.setMargins(0, 0, Ui.dp(this, 6), 0);
                srcRow.addView(srcChip, slp);
            }
            if (srcRow.getChildCount() > 0) {
                srcScroll.addView(srcRow);
                card.addView(srcScroll);
            }
        }

        // Collapsible Glass-Box Telemetry Drawer (Claude thinking x Kloster A_tau!)
        if (!msg.glassBox.isEmpty()) {
            TextView glassDetails = Ui.text(this, msg.glassBox + "\nHonesty: sentience_claimed=false · clone_claimed=false", 12f, Ui.MUTED);
            glassDetails.setPadding(Ui.dp(this, 10), Ui.dp(this, 6), Ui.dp(this, 10), Ui.dp(this, 6));
            glassDetails.setBackground(Ui.tonalPillDrawable(this, Ui.tonalWellColor(this), Ui.primaryAccent(this), 14));
            glassDetails.setVisibility(View.GONE);

            TextView glassToggle = Ui.text(this, "Glass-Box Telemetry ▸", 12f, Ui.GOLD);
            glassToggle.setPadding(0, Ui.dp(this, 2), 0, Ui.dp(this, 6));
            glassToggle.setClickable(true);
            glassToggle.setFocusable(true);
            glassToggle.setOnClickListener(v -> {
                boolean open = glassDetails.getVisibility() != View.VISIBLE;
                glassDetails.setVisibility(open ? View.VISIBLE : View.GONE);
                glassToggle.setText(open ? "glass-box telemetry ▾" : "glass-box telemetry ▸");
            });
            card.addView(glassToggle);
            card.addView(glassDetails);
        }

        // Clean Micro-Action Row (View in Dorothy 3D Brain when neuroscience-relevant + speak + copy)
        LinearLayout tools = new LinearLayout(this);
        tools.setOrientation(LinearLayout.HORIZONTAL);
        tools.setPadding(0, Ui.dp(this, 6), 0, 0);
        NeuroscienceKnowledge.NeuroAnswer neuroMatch = NeuroscienceKnowledge.lookup(msg.text);
        if (neuroMatch != null) {
            TextView brainChip = microChip("View in Dorothy 3D Brain", v -> {
                Intent openBrain = new Intent(this, BrainObservatoryActivity.class)
                        .putExtra(BrainObservatoryActivity.EXTRA_FOCUS_QUERY, neuroMatch.focusQuery);
                startActivity(openBrain);
            });
            brainChip.setTextColor(Ui.resolveColor(this, Ui.GOLD));
            tools.addView(brainChip);
        }
        tools.addView(microChip("Speak", v -> speakReply(msg.text, "zoe-repeat")));
        tools.addView(microChip("Copy", v -> copyToClipboard(msg.text)));
        card.addView(tools);
        return card;
    }

    private TextView microChip(String label, View.OnClickListener listener) {
        TextView chip = Ui.text(this, label, 12.5f, Ui.MUTED);
        chip.setPadding(Ui.dp(this, 10), Ui.dp(this, 6), Ui.dp(this, 10), Ui.dp(this, 6));
        chip.setBackground(Ui.tonalPillDrawable(this, Ui.tonalWellColor(this), Ui.primaryAccent(this), 14));
        chip.setClickable(true);
        chip.setFocusable(true);
        chip.setOnClickListener(listener);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, Ui.dp(this, 8), 0);
        chip.setLayoutParams(lp);
        return chip;
    }

    private void copyToClipboard(String text) {
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm != null) {
            cm.setPrimaryClip(ClipData.newPlainText("Zoe reply", text));
            status.setText("Copied reply to clipboard.");
        }
    }

    private void scrollChatToBottom() {
        chatScroll.post(() -> {
            if (Ui.isComfortMotionReduced()) {
                chatScroll.fullScroll(View.FOCUS_DOWN);
            } else {
                View last = chatScroll.getChildAt(0);
                int targetY = last == null ? 0 : Math.max(0, last.getBottom() - chatScroll.getHeight());
                chatScroll.smoothScrollTo(0, targetY);
            }
        });
    }

    private String lastUserPrompt() {
        for (int i = currentThread.messages.size() - 1; i >= 0; i--) {
            ChatHistoryStore.ChatMessage m = currentThread.messages.get(i);
            if ("user".equals(m.role) && !m.text.isEmpty()) {
                return m.text;
            }
        }
        return "";
    }

    private void appendMessage(ChatHistoryStore.ChatMessage msg) {
        if ("user".equals(msg.role) && currentThread.messages.isEmpty()) {
            currentThread.title = ChatHistoryStore.titleFromPrompt(msg.text);
        }
        currentThread.messages.add(msg);
        currentThread.updatedIso = ChatHistoryStore.nowIso();
        persistThreads();
        renderChatFeed();
    }

    private void persistThreads() {
        threads.remove(currentThread);
        threads.add(0, currentThread);
        while (threads.size() > ChatHistoryStore.MAX_THREADS) {
            threads.remove(threads.size() - 1);
        }
        ChatHistoryStore.save(this, threads);
    }

    private void startNewThread() {
        clearPendingPlan();
        currentThread = ChatHistoryStore.newThread();
        threads.add(0, currentThread);
        ChatHistoryStore.save(this, threads);
        renderChatFeed();
        status.setText("New chat ready");
    }

    private void clearCurrentOrAllChats() {
        clearPendingPlan();
        if (!currentThread.messages.isEmpty()) {
            currentThread.messages.clear();
            currentThread.title = "new conversation";
            ChatHistoryStore.save(this, threads);
            renderChatFeed();
            status.setText("Chat cleared");
            return;
        }
        if (threads.size() > 1) {
            new AlertDialog.Builder(this)
                    .setTitle("clear all chats?")
                    .setMessage("this deletes all " + threads.size() + " saved conversations on this device")
                    .setNegativeButton("cancel", null)
                    .setPositiveButton("clear all", (d, w) -> clearAllThreadsNow())
                    .show();
        } else {
            status.setText("Chat is already empty");
        }
    }

    private void clearAllThreadsNow() {
        clearPendingPlan();
        threads.clear();
        currentThread = ChatHistoryStore.newThread();
        threads.add(currentThread);
        ChatHistoryStore.save(this, threads);
        renderChatFeed();
        status.setText("All chats cleared");
    }

    private void showAttachAndCreateSheet() {
        String[] choices = {
                "Dorothy 3D Brain Observatory",
                "take photo (camera app)",
                "record video (camera app)",
                "choose photo from gallery",
                "choose video from gallery",
                "guided vision",
                "zoe explore"
        };
        new AlertDialog.Builder(this)
                .setTitle("add or explore")
                .setItems(choices, (d, which) -> {
                    switch (which) {
                        case 0 -> startActivity(new Intent(this, BrainObservatoryActivity.class));
                        case 1 -> launchSystemChatCapture(false);
                        case 2 -> launchSystemChatCapture(true);
                        case 3 -> pickPhotoLauncher.launch(new String[]{"image/*"});
                        case 4 -> pickVideoLauncher.launch(new String[]{"video/*"});
                        case 5 -> startActivity(new Intent(this, MainActivity.class)
                                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP)
                                .putExtra(MainActivity.EXTRA_START_VIEW, "vision"));
                        default -> startActivity(new Intent(this, ZoeLiveActivity.class)
                                .putExtra(ZoeLiveActivity.EXTRA_AUTO_START_LIVE, true));
                    }
                })
                .setNegativeButton("cancel", null)
                .show();
    }

    private void launchSystemChatCapture(boolean isVideo) {
        try {
            pendingChatCaptureUri = ZoeLearnQueue.createTempCaptureUri(
                    this, isVideo ? "chat_vid" : "chat_cam", isVideo ? "mp4" : "jpg");
            if (isVideo) {
                takeChatVideoLauncher.launch(pendingChatCaptureUri);
            } else {
                takeChatPhotoLauncher.launch(pendingChatCaptureUri);
            }
        } catch (Exception err) {
            status.setText("System Camera unavailable: " + err.getMessage());
        }
    }

    private void attachMediaUri(Uri uri, boolean isVideo) {
        status.setText(isVideo ? "Inspecting video keyframes offline…" : "Inspecting photo offline (OCR + labels)…");
        executor.execute(() -> {
            try {
                MediaChatHelper.MediaAttachment att = isVideo
                        ? MediaChatHelper.analyzeVideoUri(this, uri)
                        : MediaChatHelper.analyzePhotoUri(this, uri);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        pendingAttachment = att;
                        attachmentThumb.setImageBitmap(att.thumbnail);
                        attachmentLabel.setText(att.label + " attached · ask Zoe anything about it!");
                        attachmentBanner.setVisibility(View.VISIBLE);
                        status.setText("Attached " + att.label + ". Type a question or tap Send.");
                    }
                });
            } catch (Exception err) {
                runOnUiThread(() -> status.setText("Could not inspect media: " + err.getMessage()));
            }
        });
    }

    private void clearAttachment() {
        pendingAttachment = null;
        attachmentBanner.setVisibility(View.GONE);
    }

    private void sendTypedMessage() {
        String text = typedInput.getText() == null ? "" : typedInput.getText().toString().trim();
        if (text.isEmpty() && pendingAttachment == null) {
            return;
        }
        if (text.isEmpty()) {
            text = "video".equals(pendingAttachment.kind)
                    ? "What is happening in this video?"
                    : "What do you see in this photo?";
        }
        typedInput.setText("");
        processUserPrompt(text, false);
    }

    private void processUserPrompt(String text, boolean voiceTurn) {
        MediaChatHelper.MediaAttachment attached = pendingAttachment;
        clearAttachment();

        String displayPrompt = attached == null ? text : ("[" + attached.label + "] " + text);
        appendMessage(new ChatHistoryStore.ChatMessage("user", displayPrompt, "YOU", "", 0));
        if (attached != null) {
            handleAttachedMediaPrompt(attached, text, voiceTurn);
            return;
        }
        updatePendingActionPlan(text);

        // Explicit memory commands, sovereign identity questions & stop always answer directly via Zoe's Glass-Box Stem
        String lower = text.toLowerCase(Locale.US);
        boolean isMemoryCmd = lower.startsWith("remember ") || lower.startsWith("relay ")
                || lower.equals("recall") || lower.contains("my notes");
        boolean isIdentityQuery = lower.contains("who are you") || lower.contains("who built you")
                || lower.contains("who made you") || lower.contains("who created you")
                || lower.contains("who controls you") || lower.contains("who owns you")
                || lower.contains("who governs you") || lower.contains("who designed you")
                || lower.contains("who programmed you") || lower.contains("who trained you")
                || lower.contains("your creator") || lower.contains("are you zoe")
                || lower.contains("are you really zoe")
                || lower.contains("what is your name") || lower.contains("what's your name")
                || lower.contains("alibaba") || lower.contains("are you qwen");
        if (ConversationResponse.isStop(text)) {
            deliverLocalStem(text, "Conversation stopped. The microphone is off.", false);
            active = false;
            return;
        }
        boolean isActionCmd = !pendingPlan.isEmpty();
        boolean isOfflineNeuroQuery = NeuroscienceKnowledge.lookup(text) != null
                && !lower.contains("what if ")
                && (brainMode == BrainMode.STEM
                    || (brainMode == BrainMode.AUTO
                        && MultiAiClient.savedKey(this, MultiAiClient.activeProvider(this)).isEmpty()));
        if (isMemoryCmd || isIdentityQuery || isActionCmd || isOfflineNeuroQuery) {
            deliverLocalStem(text,
                    isOfflineNeuroQuery ? "Dorothy Neuro-Atlas" : "Zoe",
                    voiceTurn);
            return;
        }

        // Smart Hybrid Auto-Router: Cloud Frontier (if key) -> Workstation Frontier-Pro Studio (if linked) -> Local LLM -> Stem
        BrainMode effectiveMode = brainMode;
        boolean autoRouted = false;
        if (brainMode == BrainMode.AUTO) {
            autoRouted = true;
            MultiAiClient.Provider activeCloud = MultiAiClient.activeProvider(this);
            boolean hasCloudKey = !MultiAiClient.savedKey(this, activeCloud).isEmpty();
            File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
            if (hasCloudKey) {
                effectiveMode = BrainMode.CLOUD_AI;
            } else if (workstationReachable) {
                effectiveMode = BrainMode.LAB_QWEN;
            } else if (localModel != null) {
                effectiveMode = BrainMode.LOCAL_LLM;
            } else {
                effectiveMode = BrainMode.STEM;
            }
        }

        if (effectiveMode == BrainMode.STEM) {
            if (webSearchEnabled) {
                runWebOnlyStem(text, autoRouted, voiceTurn);
            } else {
                deliverLocalStem(text, "Zoe replied offline (0 cloud tokens · local stem).", voiceTurn);
            }
            return;
        }

        if (effectiveMode == BrainMode.LOCAL_LLM) {
            File modelFile = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
            if (modelFile == null) {
                if (webSearchEnabled) {
                    runWebOnlyStem(text, autoRouted, voiceTurn);
                } else {
                    deliverLocalStem(text, "no local model installed yet. replied offline via zoe stem", voiceTurn);
                }
                return;
            }
            runOnDeviceLlm(modelFile, text, autoRouted, webSearchEnabled, voiceTurn);
            return;
        }

        if (effectiveMode == BrainMode.LAB_QWEN) {
            final boolean wasAutoRouted = autoRouted;
            String endpoint = ElizaGemClient.savedEndpoint(this);
            String requestedGear = workstationFrontierReady ? "gear3" : "auto";
            String badgeTitle = workstationFrontierReady ? "Frontier Pro" : "Workstation Studio";
            status.setText(workstationFrontierReady
                    ? "Asking Frontier-Pro Zoe (" + workstationModelLabel + ")…"
                    : "Asking Workstation Studio (" + endpoint + ")…");
            addThinkingCard(badgeTitle, workstationFrontierReady ? "Thinking with Frontier Pro…" : "Asking Zoe Studio…");
            long t0 = System.currentTimeMillis();
            executor.execute(() -> {
                try {
                    ElizaGemClient.ChatReply res = studioClient.chat(endpoint, text, requestedGear);
                    long dt = System.currentTimeMillis() - t0;
                    runOnUiThread(() -> {
                        if (isFinishing() || isDestroyed()) {
                            return;
                        }
                        String safeLabReply = OnDeviceLlmEngine.enforceZoeSovereignty(res.reply);
                        String gearLabel = "gear3".equalsIgnoreCase(res.gearUsed)
                                ? "Frontier Pro"
                                : ("Studio · " + res.gearUsed);
                        String glass = "Eliza-GEM Studio · gear=" + res.gearUsed + " · mode=" + res.mode
                                + " · A_tau=" + res.aTau + "/" + res.candidateCount;
                        deliverAssistantReply(safeLabReply, gearLabel, glass, dt,
                                "Zoe replied via " + gearLabel + ".", voiceTurn, null);
                    });
                } catch (Exception fallback) {
                    workstationReachable = false;
                    workstationFrontierReady = false;
                    runOnUiThread(() -> {
                        if (!isFinishing() && !isDestroyed()) {
                            styleBrainModeStrip();
                            File localFallback = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
                            if (wasAutoRouted && localFallback != null) {
                                runOnDeviceLlm(localFallback, text, true, webSearchEnabled, voiceTurn);
                            } else {
                                deliverLocalStem(text, "workstation offline. replied locally via zoe stem", voiceTurn);
                            }
                        }
                    });
                }
            });
            return;
        }

        // CLOUD_AI mode (Multi-Turn Online SSE Streaming: Gemini / Claude / ChatGPT / Grok / Local API)
        MultiAiClient.Provider provider = MultiAiClient.activeProvider(this);
        String key = MultiAiClient.savedKey(this, provider);
        if (provider != MultiAiClient.Provider.LOCAL_OPENAI && key.isEmpty()) {
            deliverLocalStem(text, "No " + provider.displayName + " key saved. Replied offline.", voiceTurn);
            return;
        }
        runCloudStreaming(provider, text, autoRouted, webSearchEnabled, voiceTurn);
    }

    private void handleAttachedMediaPrompt(
            MediaChatHelper.MediaAttachment attached,
            String userPrompt,
            boolean voiceTurn) {
        status.setText("Analyzing " + attached.label + "…");
        long t0 = System.currentTimeMillis();
        String geminiKey = MultiAiClient.savedKey(this, MultiAiClient.Provider.GEMINI);
        File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));

        executor.execute(() -> {
            if (!geminiKey.isEmpty() && attached.jpegBytes != null && attached.jpegBytes.length > 0) {
                try {
                    String visionReply = CloudVisionClient.askVision(
                            geminiKey,
                            MultiAiClient.savedModel(this, MultiAiClient.Provider.GEMINI),
                            MultiAiClient.ZOE_SYSTEM_PROMPT + "\nUser asked: " + userPrompt
                                    + "\nAdditional offline analysis:\n" + attached.offlineReport,
                            attached.jpegBytes);
                    long dt = System.currentTimeMillis() - t0;
                    runOnUiThread(() -> {
                        if (!isFinishing() && !isDestroyed()) {
                            deliverAssistantReply(
                                    OnDeviceLlmEngine.enforceZoeSovereignty(visionReply),
                                    "GEMINI VISION · " + attached.kind.toUpperCase(Locale.US),
                                    "Multimodal Cloud Vision + Offline ML Kit · " + attached.label + " · " + dt + " ms",
                                    dt,
                                    "Analyzed " + attached.label + " with Vision.",
                                    voiceTurn,
                                    null);
                        }
                    });
                    return;
                } catch (Exception ignored) {
                }
            }
            if (localModel != null) {
                try {
                    String label = OnDeviceLlmEngine.modelLabelForFile(localModel);
                    String prompt = OnDeviceLlmEngine.buildChatMlPrompt(
                            userPrompt + "\n\nVisual observations from the user's " + attached.kind + ":\n" + attached.offlineReport,
                            currentThread.messages, buildMemorySummary(), "");
                    String reply = localLlm.generateStreaming(localModel, prompt, null);
                    long dt = System.currentTimeMillis() - t0;
                    runOnUiThread(() -> {
                        if (!isFinishing() && !isDestroyed()) {
                            deliverAssistantReply(
                                    reply,
                                    label + " · " + attached.kind.toUpperCase(Locale.US),
                                    "ML Kit + " + label + " · " + attached.label + " · " + dt + " ms",
                                    dt,
                                    "Analyzed " + attached.label + ".",
                                    voiceTurn,
                                    null);
                        }
                    });
                    return;
                } catch (Exception ignored) {
                }
            }
            long dt = System.currentTimeMillis() - t0;
            String stemReply = "Offline " + attached.label + " inspection:\n\n" + attached.offlineReport
                    + "\n\n(Add a Gemini API key in ⚙ Brain or install Zoe Local 1.5B for deeper visual Q&A.)";
            runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed()) {
                    deliverAssistantReply(stemReply, "ZOE VISION · OFFLINE",
                            "Bundled ML Kit OCR + Labels · " + attached.label, dt,
                            "Inspected " + attached.label + " offline.", voiceTurn, null);
                }
            });
        });
    }

    private void addThinkingCard(String badge, String placeholder) {
        LinearLayout card = Ui.vertical(this);
        card.setBackground(Ui.cardBackground(this, 22));
        card.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, Ui.dp(this, 4), Ui.dp(this, 12), Ui.dp(this, 8));
        card.addView(Ui.text(this, ZOE_CREST + "  ·  " + badge, 12f, Ui.COBALT));
        TextView thinking = Ui.text(this, placeholder, 15f, Ui.MUTED);
        thinking.setPadding(0, Ui.dp(this, 6), 0, 0);
        card.addView(thinking);
        chatFeed.addView(card, lp);
        scrollChatToBottom();
    }

    private void runWebOnlyStem(String prompt, boolean autoRouted, boolean voiceTurn) {
        status.setText("Searching live public web sources (HTTPS · zero trackers)…");
        addThinkingCard("Live Web", "Checking verified public sources…");
        long t0 = System.currentTimeMillis();
        executor.execute(() -> {
            WebSearchClient.SearchResult sr = WebSearchClient.search(prompt);
            long dt = System.currentTimeMillis() - t0;
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) {
                    return;
                }
                if (sr.hasSources()) {
                    String routeTag = autoRouted ? "⚡ AUTO → LIVE WEB" : "ZOE LIVE WEB";
                    String glass = (autoRouted ? "Auto-Router → " : "") + "DuckDuckGo + Wikipedia · "
                            + sr.sources.size() + " verified HTTPS sources · " + dt + " ms";
                    deliverAssistantReply(sr.formatFallbackAnswer(), routeTag, glass, dt,
                            "Live Web grounded (" + sr.sources.size() + " sources).", voiceTurn, sr.toSourceBadges());
                } else {
                    deliverLocalStem(prompt, "no direct web summary found. replied offline", voiceTurn);
                }
            });
        });
    }

    private void runCloudStreaming(
            MultiAiClient.Provider provider,
            String prompt,
            boolean autoRouted,
            boolean useWeb,
            boolean voiceTurn) {
        String model = MultiAiClient.savedModel(this, provider);
        String providerBadge = shortProviderName(provider).toUpperCase(Locale.US) + " · " + model;
        status.setText((useWeb ? "Searching live web + streaming " : "Streaming ") + provider.displayName + " (" + model + ")…");

        LinearLayout streamCard = Ui.vertical(this);
        streamCard.setBackground(Ui.cardBackground(this, 22));
        streamCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, Ui.dp(this, 4), Ui.dp(this, 12), Ui.dp(this, 8));
        streamCard.addView(Ui.text(this, ZOE_CREST + "  ·  " + providerBadge + "…", 12f, Ui.COBALT));
        TextView streamBody = Ui.text(this, useWeb ? "Gathering live citations & thinking…" : "Streaming live…", 15.5f, Ui.TEXT);
        streamBody.setPadding(0, Ui.dp(this, 8), 0, 0);
        streamCard.addView(streamBody);
        chatFeed.addView(streamCard, lp);
        scrollChatToBottom();

        List<ChatHistoryStore.ChatMessage> historySnapshot = new ArrayList<>(currentThread.messages);
        String memCtx = buildMemorySummary();
        long t0 = System.currentTimeMillis();
        executor.execute(() -> {
            WebSearchClient.SearchResult webRes = useWeb ? WebSearchClient.search(prompt) : null;
            String webCtx = (webRes != null && webRes.hasSources()) ? webRes.formatContextForPrompt(1200) : "";
            List<String> badges = (webRes != null && webRes.hasSources()) ? webRes.toSourceBadges() : null;
            try {
                String reply = MultiAiClient.askStreaming(
                        this, provider, prompt, historySnapshot, memCtx, webCtx, useWeb,
                        partial -> runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed() && !partial.isEmpty()) {
                                streamBody.setText(partial);
                                scrollChatToBottom();
                            }
                        }));
                long dt = System.currentTimeMillis() - t0;
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        String glass = (autoRouted ? "Auto-Router → " : "")
                                + "Provider: " + provider.displayName + " · Model: " + model
                                + " · Multi-turn SSE"
                                + (webRes != null && webRes.hasSources() ? " · Live Web (" + webRes.sources.size() + " sources)" : "");
                        deliverAssistantReply(reply, providerBadge + (useWeb ? " · WEB" : ""), glass, dt,
                                provider.displayName + " finished streaming" + (useWeb ? " (web-grounded)." : "."),
                                voiceTurn, badges);
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        File localFallback = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
                        if (autoRouted && localFallback != null) {
                            runOnDeviceLlm(localFallback, prompt, true, false, voiceTurn);
                        } else {
                            deliverLocalStem(prompt, provider.displayName + " unavailable. Replied offline.", voiceTurn);
                        }
                    }
                });
            }
        });
    }

    private void runOnDeviceLlm(
            File modelFile,
            String prompt,
            boolean autoRouted,
            boolean useWeb,
            boolean voiceTurn) {
        String label = OnDeviceLlmEngine.modelLabelForFile(modelFile);
        status.setText(useWeb
                ? "Searching live web + running " + label + " on-device…"
                : "Running " + label + " offline on this phone…");

        LinearLayout streamCard = Ui.vertical(this);
        streamCard.setBackground(Ui.cardBackground(this, 22));
        streamCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, Ui.dp(this, 4), Ui.dp(this, 12), Ui.dp(this, 8));
        streamCard.addView(Ui.text(this, ZOE_CREST + "  ·  " + label + (useWeb ? " · Web…" : " · Offline…"), 12f, Ui.GREEN));
        TextView streamBody = Ui.text(this, useWeb ? "Fetching live public sources & thinking locally…" : "Thinking locally…", 15.5f, Ui.TEXT);
        streamBody.setPadding(0, Ui.dp(this, 8), 0, 0);
        streamCard.addView(streamBody);
        chatFeed.addView(streamCard, lp);
        scrollChatToBottom();

        List<ChatHistoryStore.ChatMessage> historySnapshot = new ArrayList<>(currentThread.messages);
        String memCtx = buildMemorySummary();
        final byte[] attachedPhotoBytes = (pendingAttachment != null && pendingAttachment.jpegBytes != null && pendingAttachment.jpegBytes.length > 0)
                ? pendingAttachment.jpegBytes : null;
        long t0 = System.currentTimeMillis();
        executor.execute(() -> {
            WebSearchClient.SearchResult webRes = useWeb ? WebSearchClient.search(prompt) : null;
            String webCtx = (webRes != null && webRes.hasSources()) ? webRes.formatContextForPrompt(700) : "";
            List<String> badges = (webRes != null && webRes.hasSources()) ? webRes.toSourceBadges() : null;
            String formatted = OnDeviceLlmEngine.buildChatMlPrompt(prompt, historySnapshot, memCtx, webCtx);
            android.graphics.Bitmap optBmp = null;
            if (attachedPhotoBytes != null && OnDeviceLlmEngine.supportsNativeVision(modelFile)) {
                optBmp = android.graphics.BitmapFactory.decodeByteArray(attachedPhotoBytes, 0, attachedPhotoBytes.length);
            }
            try {
                String finalReply = localLlm.generateStreamingWithOptionalImage(modelFile, formatted, optBmp, (partial, done) ->
                        runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed() && !partial.isEmpty()) {
                                streamBody.setText(partial);
                                scrollChatToBottom();
                            }
                        }));
                long dt = System.currentTimeMillis() - t0;
                String rtLabel = OnDeviceLlmEngine.runtimeTelemetryLabel();
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        String clean = finalReply.isEmpty() ? "(No output generated.)" : finalReply;
                        boolean grounded = webRes != null && webRes.hasSources();
                        String cardTitle = grounded ? (label + " · WEB") : label;
                        String glass = (autoRouted ? "Auto-Router → " : "") + label
                                + " (" + rtLabel + ") · On-Device MediaPipe GenAI · 0 cloud AI tokens"
                                + (grounded ? " · Live Web (" + webRes.sources.size() + " sources)" : "")
                                + " · " + dt + " ms";
                        deliverAssistantReply(clean, cardTitle, glass, dt,
                                grounded ? (label + " finished with " + webRes.sources.size() + " live web sources.")
                                        : (label + " finished offline (" + rtLabel + " · 0 cloud tokens)."),
                                voiceTurn, badges);
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        deliverLocalStem(prompt, "local model error. replied via zoe stem", voiceTurn);
                    }
                });
            } finally {
                if (optBmp != null && !optBmp.isRecycled()) {
                    optBmp.recycle();
                }
            }
        });
    }

    private void deliverLocalStem(String input, String statusNote, boolean voiceTurn) {
        long t0 = System.currentTimeMillis();
        ZoeBrainEngine.BrainReply res = brain.respond(input);
        long dt = Math.max(1L, System.currentTimeMillis() - t0);
        String badge = (res.brainFocusQuery != null && !res.brainFocusQuery.isEmpty())
                ? "Dorothy Neuro-Atlas"
                : "Zoe";
        deliverAssistantReply(res.reply, badge, res.telemetryBadge() + " · " + res.citation, dt,
                statusNote == null ? "" : statusNote, voiceTurn, null);
    }

    private void deliverAssistantReply(
            String reply,
            String providerBadge,
            String glassBox,
            long latencyMs,
            String statusNote,
            boolean voiceTurn) {
        deliverAssistantReply(reply, providerBadge, glassBox, latencyMs, statusNote, voiceTurn, null);
    }

    private void deliverAssistantReply(
            String reply,
            String providerBadge,
            String glassBox,
            long latencyMs,
            String statusNote,
            boolean voiceTurn,
            List<String> sources) {
        lastResponse = reply;
        appendMessage(new ChatHistoryStore.ChatMessage("zoe", reply, providerBadge, glassBox, latencyMs, sources));
        status.setText(statusNote == null ? "" : statusNote);
        if (!captionMode) {
            if (voiceTurn && active) {
                speakThenListen(reply);
            } else {
                speakReply(reply, "zoe-typed");
            }
        }
    }

    private String buildMemorySummary() {
        List<ZoeBrainEngine.MemoryNote> notes = brain.notesSnapshot();
        if (notes.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        int start = Math.max(0, notes.size() - 4);
        for (int i = start; i < notes.size(); i++) {
            sb.append("- ").append(notes.get(i).text).append('\n');
        }
        return sb.toString().trim();
    }

    // --- Approval-Gated Multi-Step Phone Action Plan ---

    private void updatePendingActionPlan(String input) {
        List<OsToolsBridge.ActionSuggestion> plan = OsToolsBridge.parseActionPlan(input);
        if (plan.isEmpty()) {
            return;
        }
        pendingPlan.clear();
        pendingPlan.addAll(plan);
        extraPlanSteps.removeAllViews();

        OsToolsBridge.ActionSuggestion first = plan.get(0);
        osActionBtn.setText(plan.size() > 1 ? "Step 1: " + first.label : first.label);
        for (int i = 1; i < plan.size(); i++) {
            OsToolsBridge.ActionSuggestion step = plan.get(i);
            Button stepBtn = Ui.button(this, "Step " + (i + 1) + ": " + step.label,
                    Ui.GREEN, v -> executeAction(step));
            extraPlanSteps.addView(stepBtn);
        }
        osActionBar.setVisibility(View.VISIBLE);
        scrollChatToBottom();
    }

    private void clearPendingPlan() {
        pendingPlan.clear();
        extraPlanSteps.removeAllViews();
        osActionBar.setVisibility(View.GONE);
    }

    private void executeAction(OsToolsBridge.ActionSuggestion act) {
        if (act == null || !act.isActionable()) {
            return;
        }
        try {
            switch (act.kind) {
                case NAVIGATE -> {
                    Intent nav = new Intent(Intent.ACTION_VIEW,
                            Uri.parse(OsToolsBridge.androidNavigationUri(act.query)));
                    nav.setPackage(OsToolsBridge.GOOGLE_MAPS_PACKAGE);
                    try {
                        startActivity(nav);
                    } catch (ActivityNotFoundException fallback) {
                        startActivity(new Intent(Intent.ACTION_VIEW,
                                Uri.parse(OsToolsBridge.googleMapsSearchUrl(act.query))));
                    }
                    status.setText("Opened Google Maps navigation for " + act.query + ".");
                }
                case MAP_SEARCH -> {
                    Intent search = new Intent(Intent.ACTION_VIEW,
                            Uri.parse(OsToolsBridge.androidGeoSearchUri(act.query, 0, 0, false)));
                    try {
                        startActivity(search);
                    } catch (ActivityNotFoundException fallback) {
                        startActivity(new Intent(Intent.ACTION_VIEW,
                                Uri.parse(OsToolsBridge.googleMapsSearchUrl(act.query))));
                    }
                    status.setText("Opened Maps search for " + act.query + ".");
                }
                case OPEN_LOCATION -> {
                    Intent map = new Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0"));
                    try {
                        startActivity(map);
                    } catch (ActivityNotFoundException fallback) {
                        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://maps.google.com")));
                    }
                    status.setText("Opened Maps.");
                }
                case OPEN_SAFETY -> {
                    PackageManager pm = getPackageManager();
                    Intent hub = pm.getLaunchIntentForPackage(OsToolsBridge.PIXEL_SAFETY_PACKAGE);
                    if (hub == null) {
                        hub = pm.getLaunchIntentForPackage(OsToolsBridge.ANDROID_EMERGENCY_PACKAGE);
                    }
                    startActivity(hub != null ? hub : new Intent(Intent.ACTION_DIAL, Uri.parse("tel:911")));
                    status.setText("Opened Personal Safety.");
                }
                case TOGGLE_TORCH -> toggleTalkFlashlight();
                case SET_TIMER -> {
                    Intent timer = new Intent(AlarmClock.ACTION_SET_TIMER)
                            .putExtra(AlarmClock.EXTRA_LENGTH, act.seconds)
                            .putExtra(AlarmClock.EXTRA_MESSAGE, "Zoe timer");
                    startActivity(timer);
                    status.setText("Opened Clock to start your timer.");
                }
                case SET_ALARM -> {
                    Intent alarm = new Intent(AlarmClock.ACTION_SET_ALARM)
                            .putExtra(AlarmClock.EXTRA_HOUR, act.hour)
                            .putExtra(AlarmClock.EXTRA_MINUTES, act.minute)
                            .putExtra(AlarmClock.EXTRA_MESSAGE, "Zoe alarm");
                    startActivity(alarm);
                    status.setText("Opened Clock to set your alarm.");
                }
                default -> { }
            }
        } catch (ActivityNotFoundException error) {
            status.setText("No built-in app was available for that action on this device.");
        }
    }

    private void toggleTalkFlashlight() {
        CameraManager cm = (CameraManager) getSystemService(Context.CAMERA_SERVICE);
        if (cm == null) {
            status.setText("Flashlight is unavailable on this device.");
            return;
        }
        try {
            for (String id : cm.getCameraIdList()) {
                CameraCharacteristics chars = cm.getCameraCharacteristics(id);
                if (Boolean.TRUE.equals(chars.get(CameraCharacteristics.FLASH_INFO_AVAILABLE))) {
                    talkTorchOn = !talkTorchOn;
                    cm.setTorchMode(id, talkTorchOn);
                    status.setText(talkTorchOn ? "Flashlight turned on." : "Flashlight turned off.");
                    return;
                }
            }
            status.setText("No flashlight hardware found on this device.");
        } catch (Exception error) {
            status.setText("Could not toggle flashlight: " + error.getMessage());
        }
    }

    // --- Settings Sheet (Brain Mode, Web, Captions, Voice Picker, Offline Models, Cloud Keys & Sync) ---

    private void showBrainCouncilSheet() {
        ScrollView sv = new ScrollView(this);
        LinearLayout box = Ui.vertical(this);
        box.setBackground(Ui.cardBackground(this, 26));
        box.setPadding(Ui.dp(this, 18), Ui.dp(this, 18), Ui.dp(this, 18), Ui.dp(this, 18));

        TextView heading = Ui.text(this, "Chat Settings", 20f, Ui.TEXT);
        heading.setTypeface(Ui.SANS_MEDIUM);
        box.addView(heading);

        // Section 0: Brain mode, live web & captions (cleanly tucked here instead of cluttering the top bar!)
        box.addView(Ui.section(this, "Mode & Web"));
        HorizontalScrollView modeStrip = new HorizontalScrollView(this);
        modeStrip.setHorizontalScrollBarEnabled(false);
        LinearLayout modeRow = new LinearLayout(this);
        modeRow.setOrientation(LinearLayout.HORIZONTAL);
        modeRow.setGravity(Gravity.CENTER_VERTICAL);
        modeAutoBtn = modeChip("Auto", v -> selectBrainMode(BrainMode.AUTO));
        modeAutoBtn.setId(R.id.conversation_mode_auto);
        modeLocalLlmBtn = modeChip("Local", v -> selectBrainMode(BrainMode.LOCAL_LLM));
        modeLocalLlmBtn.setId(R.id.conversation_mode_local_llm);
        modeLabBtn = modeChip("Lab", v -> selectBrainMode(BrainMode.LAB_QWEN));
        modeLabBtn.setId(R.id.conversation_mode_lab);
        modeCloudBtn = modeChip("Cloud", v -> selectBrainMode(BrainMode.CLOUD_AI));
        modeCloudBtn.setId(R.id.conversation_mode_cloud);
        modeStemBtn = modeChip("Stem", v -> selectBrainMode(BrainMode.STEM));
        modeStemBtn.setId(R.id.conversation_mode_stem);
        webToggleBtn = modeChip(webSearchEnabled ? "Web: On" : "Web: Off", v -> toggleWebSearch());
        webToggleBtn.setId(R.id.conversation_web_toggle);
        for (Button b : new Button[]{modeAutoBtn, modeLocalLlmBtn, webToggleBtn, modeLabBtn, modeCloudBtn, modeStemBtn}) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
            lp.setMargins(0, 0, Ui.dp(this, 6), 0);
            modeRow.addView(b, lp);
        }
        modeStrip.addView(modeRow);
        box.addView(modeStrip);
        styleBrainModeStrip();

        // Voice & Captions
        box.addView(Ui.section(this, "Voice & Captions"));
        captionToggle = Ui.button(this, captionMode ? "Caption Mode: On" : "Caption Mode: Off", Ui.COBALT, v -> {
            captionMode = !captionMode;
            captionToggle.setText(captionMode ? "Caption Mode: On" : "Caption Mode: Off");
            status.setText(captionMode ? "Caption mode on" : "Conversation mode on");
        });
        captionToggle.setId(R.id.conversation_captions);
        box.addView(captionToggle);

        voicePicker = new Spinner(this);
        voicePicker.setId(R.id.conversation_voice);
        voicePicker.setContentDescription("Choose an installed English voice");
        bindVoicePickerAdapter();
        box.addView(voicePicker);

        // Section A: On-Device Offline Neural LLM (MediaPipe GenAI)
        box.addView(Ui.section(this, "On-Device Models (Offline)"));
        TextView llmStatus = Ui.text(this, localLlmStatusSummary(), 13.5f, Ui.MUTED);
        box.addView(llmStatus);

        for (OnDeviceLlmEngine.ModelSpec spec : OnDeviceLlmEngine.ModelSpec.values()) {
            boolean installed = OnDeviceLlmEngine.isInstalled(this, spec);
            String label = (installed ? "Use " : "Download ") + spec.label;
            Button mBtn = Ui.button(this, label, installed ? Ui.GREEN : Ui.COBALT, v -> {
                OnDeviceLlmEngine.saveSelectedModel(this, spec);
                if (OnDeviceLlmEngine.isInstalled(this, spec)) {
                    brainMode = BrainMode.LOCAL_LLM;
                    styleBrainModeStrip();
                    llmStatus.setText("Selected installed model: " + spec.label);
                    status.setText("Local model ready (" + spec.label + ")");
                } else {
                    llmStatus.setText("Downloading " + spec.label + "... 0%");
                    v.setEnabled(false);
                    executor.execute(() -> {
                        try {
                            localLlm.downloadModel(spec, (pct, dlMb, totMb) -> runOnUiThread(() ->
                                    llmStatus.setText("Downloading " + spec.id + ": " + pct + "% (" + dlMb + "/" + totMb + " MB)")));
                            runOnUiThread(() -> {
                                if (!isFinishing() && !isDestroyed()) {
                                    brainMode = BrainMode.LOCAL_LLM;
                                    styleBrainModeStrip();
                                    llmStatus.setText("Installed offline: " + spec.label);
                                    status.setText("Local model installed (" + spec.id + ")");
                                    ((Button) v).setText("Use " + spec.label);
                                    v.setEnabled(true);
                                }
                            });
                        } catch (Exception err) {
                            runOnUiThread(() -> {
                                llmStatus.setText("Download stopped: " + err.getMessage());
                                v.setEnabled(true);
                            });
                        }
                    });
                }
            });
            box.addView(mBtn);
        }

        // Section B: Optional Cloud BYOK Keys
        box.addView(Ui.section(this, "Cloud Keys (Optional)"));
        Spinner providerSpinner = new Spinner(this);
        MultiAiClient.Provider[] allProviders = MultiAiClient.Provider.values();
        String[] providerNames = new String[allProviders.length];
        MultiAiClient.Provider currentProv = MultiAiClient.activeProvider(this);
        int selectedIdx = 0;
        for (int i = 0; i < allProviders.length; i++) {
            boolean hasKey = !MultiAiClient.savedKey(this, allProviders[i]).isEmpty();
            providerNames[i] = allProviders[i].displayName + (hasKey ? " ✓" : "");
            if (allProviders[i] == currentProv) {
                selectedIdx = i;
            }
        }
        providerSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, providerNames));
        providerSpinner.setSelection(selectedIdx);
        box.addView(providerSpinner);

        EditText keyField = Ui.input(this, MultiAiClient.savedKey(this, currentProv), "Optional API Key (stays private on device)");
        EditText modelField = Ui.input(this, MultiAiClient.savedModel(this, currentProv), "Model ID");
        box.addView(keyField);
        box.addView(modelField);

        providerSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int pos, long id) {
                MultiAiClient.Provider chosen = allProviders[pos];
                keyField.setText(MultiAiClient.savedKey(ConversationActivity.this, chosen));
                modelField.setText(MultiAiClient.savedModel(ConversationActivity.this, chosen));
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) { }
        });

        Button saveProviderBtn = Ui.primaryButton(this, "Save & Activate", Ui.COBALT, v -> {
            MultiAiClient.Provider chosen = allProviders[providerSpinner.getSelectedItemPosition()];
            MultiAiClient.saveActiveProvider(this, chosen);
            MultiAiClient.saveKey(this, chosen, keyField.getText().toString());
            MultiAiClient.saveModel(this, chosen, modelField.getText().toString());
            brainMode = BrainMode.CLOUD_AI;
            styleBrainModeStrip();
            status.setText("Saved " + chosen.displayName);
        });
        box.addView(saveProviderBtn);

        // Section C: Zoe Voice, Sing & Sync
        box.addView(Ui.section(this, "Voice & Lab Sync"));
        Button voiceToggle = Ui.button(this, useNativeVoice ? "Voice: Zoe Synth" : "Voice: OS TTS", Ui.COBALT, v -> {
            useNativeVoice = !useNativeVoice;
            ((Button) v).setText(useNativeVoice ? "Voice: Zoe Synth" : "Voice: OS TTS");
            status.setText(useNativeVoice ? "Zoe Synth voice active" : "OS voice active");
        });
        Button singBtn = Ui.button(this, "Sing Zoe", Ui.RUBY, v -> playZoeSong());
        box.addView(Ui.buttonRow(this, voiceToggle, singBtn));

        Button syncMemBtn = Ui.button(this, "Sync Memory", Ui.GOLD, v -> syncMemoryToLab());
        Button exportBtn = Ui.button(this, "Share Transcript", Ui.CYAN, v -> shareTranscript());
        box.addView(Ui.buttonRow(this, syncMemBtn, exportBtn));

        final AlertDialog dialog = new AlertDialog.Builder(this).setView(sv).create();
        Button closeBtn = Ui.button(this, "Done", Ui.MUTED, v -> dialog.dismiss());
        box.addView(closeBtn);
        sv.addView(box);
        dialog.show();
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }
    }

    private String localLlmStatusSummary() {
        File installed = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
        if (installed != null) {
            return "Installed offline: " + OnDeviceLlmEngine.modelLabelForFile(installed)
                    + " (" + (installed.length() / (1024L * 1024L)) + " MB)";
        }
        return "No local model downloaded yet · Pick 0.5B Fast or 1.5B Pro below";
    }

    private void showThreadsSheet() {
        ScrollView sv = new ScrollView(this);
        LinearLayout box = Ui.vertical(this);
        box.setBackground(Ui.cardBackground(this, 26));
        box.setPadding(Ui.dp(this, 18), Ui.dp(this, 18), Ui.dp(this, 18), Ui.dp(this, 18));

        TextView heading = Ui.text(this, "Conversations (" + threads.size() + ")", 19f, Ui.TEXT);
        heading.setTypeface(Ui.SANS_MEDIUM);
        heading.setPadding(0, 0, 0, Ui.dp(this, 10));
        box.addView(heading);

        final AlertDialog dialog = new AlertDialog.Builder(this).setView(sv).create();

        for (int i = 0; i < threads.size(); i++) {
            final ChatHistoryStore.ChatThread t = threads.get(i);
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setBackground(Ui.tonalPillDrawable(this, Ui.tonalWellColor(this),
                    t == currentThread ? Ui.primaryAccent(this) : Ui.dividerColor(this), 16));
            row.setPadding(Ui.dp(this, 12), Ui.dp(this, 8), Ui.dp(this, 8), Ui.dp(this, 8));

            TextView titleTv = Ui.text(this,
                    t.title + " (" + t.messages.size() + ")",
                    14f, t == currentThread ? Ui.TEXT : Ui.MUTED);
            titleTv.setMaxLines(1);
            titleTv.setEllipsize(android.text.TextUtils.TruncateAt.END);
            titleTv.setClickable(true);
            titleTv.setOnClickListener(v -> {
                currentThread = t;
                renderChatFeed();
                status.setText("Opened " + currentThread.title);
                dialog.dismiss();
            });
            row.addView(titleTv, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            Button delBtn = Ui.tonalIconButton(this, "✕", "Delete conversation", v -> {
                threads.remove(t);
                if (threads.isEmpty()) {
                    currentThread = ChatHistoryStore.newThread();
                    threads.add(currentThread);
                } else if (currentThread == t) {
                    currentThread = threads.get(0);
                }
                ChatHistoryStore.save(this, threads);
                renderChatFeed();
                status.setText("deleted conversation");
                dialog.dismiss();
            });
            delBtn.setTextSize(14f);
            row.addView(delBtn, new LinearLayout.LayoutParams(Ui.dp(this, 36), Ui.dp(this, 36)));

            LinearLayout.LayoutParams rlp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            rlp.setMargins(0, 0, 0, Ui.dp(this, 6));
            box.addView(row, rlp);
        }

        Button newBtn = Ui.primaryButton(this, "+ new chat", Ui.COBALT, v -> {
            dialog.dismiss();
            startNewThread();
        });
        Button clearAllBtn = Ui.button(this, "clear all", Ui.RUBY, v -> {
            dialog.dismiss();
            clearAllThreadsNow();
        });
        box.addView(Ui.buttonRow(this, newBtn, clearAllBtn));

        Button closeBtn = Ui.button(this, "close", Ui.MUTED, v -> dialog.dismiss());
        box.addView(closeBtn);
        sv.addView(box);
        dialog.show();
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }
    }

    // --- Voice / Speech Recognition / TTS / Native Formant Voice ---

    private void loadVoices() {
        voices.clear();
        if (textToSpeech == null) {
            return;
        }
        Set<Voice> available = textToSpeech.getVoices();
        if (available != null) {
            for (Voice v : available) {
                if (v != null && v.getLocale() != null && "en".equalsIgnoreCase(v.getLocale().getLanguage())
                        && !v.isNetworkConnectionRequired()) {
                    voices.add(v);
                }
            }
        }
        voices.sort((a, b) -> {
            boolean aUs = "US".equalsIgnoreCase(a.getLocale().getCountry());
            boolean bUs = "US".equalsIgnoreCase(b.getLocale().getCountry());
            if (aUs != bUs) {
                return aUs ? -1 : 1;
            }
            int q = Integer.compare(b.getQuality(), a.getQuality());
            return q != 0 ? q : a.getName().compareTo(b.getName());
        });
        bindVoicePickerAdapter();
    }

    private void bindVoicePickerAdapter() {
        if (voicePicker == null) {
            return;
        }
        List<String> names = new ArrayList<>();
        if (voices.isEmpty()) {
            names.add("default voice");
        } else {
            java.util.Map<String, Integer> regionCounts = new java.util.HashMap<>();
            for (Voice v : voices) {
                String country = v.getLocale().getCountry();
                String region = country == null || country.isEmpty() ? "English" : "English (" + country + ")";
                int idx = regionCounts.getOrDefault(region, 0) + 1;
                regionCounts.put(region, idx);
                names.add(idx == 1 ? "voice: " + region : "voice: " + region + " #" + idx);
            }
        }
        voicePicker.setAdapter(Ui.spinnerAdapter(this, names));
        if (selectedVoiceIndex >= 0 && selectedVoiceIndex < names.size()) {
            voicePicker.setSelection(selectedVoiceIndex);
        }
        voicePicker.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int pos, long id) {
                selectedVoiceIndex = pos;
                if (textToSpeech != null && pos >= 0 && pos < voices.size()) {
                    textToSpeech.setVoice(voices.get(pos));
                }
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) { }
        });
    }

    private void speakReply(String text, String utteranceId) {
        if (text == null || text.isBlank()) {
            return;
        }
        if (useNativeVoice) {
            nativeVoice.speak(text, () -> onNativeSpeechFinished(utteranceId));
            return;
        }
        if (ttsReady && textToSpeech != null) {
            textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId);
        }
    }

    private void onNativeSpeechFinished(String utteranceId) {
        runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed() && active && "zoe-turn".equals(utteranceId)) {
                startListening();
            }
        });
    }

    private void playZoeSong() {
        status.setText("Singing Zoe's native soprano theme (44.1 kHz DSP, offline)…");
        nativeVoice.singZoe(null);
    }

    private void syncMemoryToLab() {
        List<ZoeBrainEngine.MemoryNote> notes = brain.notesSnapshot();
        if (notes.isEmpty()) {
            status.setText("No local notes to sync yet. Type `remember ...` first.");
            return;
        }
        String endpoint = ElizaGemClient.savedEndpoint(this);
        status.setText("Syncing " + notes.size() + " private notes to " + endpoint + "…");
        executor.execute(() -> {
            try {
                ElizaGemClient.SyncResult res = studioClient.syncMemory(endpoint, Build.MODEL, notes);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Unified memory synced: " + res.accepted + " added, " + res.deduplicated + " existing.");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Lab sync unreachable (" + error.getMessage() + "). Notes stay safe on this phone.");
                    }
                });
            }
        });
    }

    private void shareTranscript() {
        if (currentThread.messages.isEmpty()) {
            status.setText("No conversation messages to share yet.");
            return;
        }
        StringBuilder sb = new StringBuilder();
        for (ChatHistoryStore.ChatMessage m : currentThread.messages) {
            sb.append("user".equals(m.role) ? "YOU: " : "ZOE: ").append(m.text).append("\n\n");
        }
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_SUBJECT, "Zoe conversation · " + currentThread.title)
                .putExtra(Intent.EXTRA_TEXT, sb.toString().trim());
        startActivity(Intent.createChooser(share, "Share Zoe conversation"));
    }

    private void startConversation() {
        if (active) {
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.RECORD_AUDIO}, MICROPHONE_PERMISSION);
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            status.setText("No speech-recognition service is available on this device. You can still type below.");
            return;
        }
        active = true;
        if (captionMode) {
            startListening();
            return;
        }
        if (!ttsReady) {
            startWhenReady = true;
            status.setText("Preparing Zoe's voice…");
            return;
        }
        speakThenListen(lastResponse);
    }

    private void speakThenListen(String response) {
        if (!active) {
            return;
        }
        lastResponse = response;
        status.setText("Zoe is speaking…");
        speakReply(response, "zoe-turn");
    }

    private void startListening() {
        if (!active) {
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            active = false;
            status.setText("Speech recognition is unavailable.");
            return;
        }
        destroyRecognizer();
        if (Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) {
            recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(this);
            status.setText("On-device speech selected. Your turn…");
        } else {
            recognizer = SpeechRecognizer.createSpeechRecognizer(this);
            status.setText("Offline speech preferred. Your turn…");
        }
        recognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle params) { }
            @Override public void onBeginningOfSpeech() { }
            @Override public void onRmsChanged(float rmsdB) { }
            @Override public void onBufferReceived(byte[] buffer) { }
            @Override public void onEndOfSpeech() { }
            @Override public void onPartialResults(Bundle partialResults) { }
            @Override public void onEvent(int eventType, Bundle params) { }

            @Override
            public void onError(int error) {
                if (active) {
                    active = false;
                    status.setText(speechErrorLabel(error));
                }
            }

            @Override
            public void onResults(Bundle results) {
                if (!active) {
                    return;
                }
                ArrayList<String> alternatives = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (alternatives == null || alternatives.isEmpty()) {
                    status.setText("Nothing was recognized. Your turn again…");
                    startListening();
                    return;
                }
                String heard = alternatives.get(0);
                if (captionMode) {
                    appendMessage(new ChatHistoryStore.ChatMessage("user", "[CAPTION] " + heard, "CAPTION", "", 0));
                    startListening();
                    return;
                }
                processUserPrompt(heard, true);
            }
        });
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
                .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);
        try {
            recognizer.startListening(intent);
        } catch (RuntimeException error) {
            active = false;
            status.setText("Listening could not start: " + error.getMessage());
        }
    }

    static String speechErrorLabel(int error) {
        return switch (error) {
            case SpeechRecognizer.ERROR_AUDIO -> "Audio recording error (code 3). No command was executed.";
            case SpeechRecognizer.ERROR_CLIENT -> "Speech client stopped (code 5). No command was executed.";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission is required (code 9).";
            case SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT ->
                    "Speech service network error (code " + error + "). Type below anytime.";
            case SpeechRecognizer.ERROR_NO_MATCH -> "No speech match (code 7). Tap Start talking to try again.";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Speech recognizer is busy (code 8). Try again shortly.";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech heard (code 6). Tap Start talking when ready.";
            default -> "Speech recognition ended (code " + error + ").";
        };
    }

    private void stopConversation() {
        active = false;
        startWhenReady = false;
        destroyRecognizer();
        if (textToSpeech != null) {
            textToSpeech.stop();
        }
        if (nativeVoice != null) {
            nativeVoice.stop();
        }
        status.setText("Conversation stopped · Microphone is off");
    }

    private void destroyRecognizer() {
        if (recognizer != null) {
            try {
                recognizer.cancel();
                recognizer.destroy();
            } catch (RuntimeException ignored) {
            }
            recognizer = null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == MICROPHONE_PERMISSION) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                startConversation();
            } else {
                status.setText("Microphone permission was not granted. You can still type below.");
            }
        }
    }

    @Override
    protected void onPause() {
        if (active) {
            stopConversation();
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        stopConversation();
        if (textToSpeech != null) {
            textToSpeech.shutdown();
            textToSpeech = null;
        }
        if (localLlm != null) {
            localLlm.cancelDownload();
            localLlm.close();
        }
        executor.shutdownNow();
        super.onDestroy();
    }
}
