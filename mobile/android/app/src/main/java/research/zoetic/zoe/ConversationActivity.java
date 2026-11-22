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
import android.view.View;
import android.view.ViewGroup;
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
    private String lastResponse = "Hi, I'm Zoe. What would you like to explore?";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        brain = new ZoeBrainEngine(this);
        nativeVoice = new ZoeNativeVoice();
        localLlm = new OnDeviceLlmEngine(this);

        threads.addAll(ChatHistoryStore.load(this));
        if (threads.isEmpty()) {
            currentThread = ChatHistoryStore.newThread();
            threads.add(0, currentThread);
        } else {
            currentThread = threads.get(0);
        }

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        // 1. Compact Header + Threads / New / Brain Settings
        LinearLayout headerWrap = Ui.vertical(this);
        headerWrap.setBackgroundColor(Color.TRANSPARENT);
        headerWrap.setPadding(Ui.dp(this, 14), Ui.dp(this, 6), Ui.dp(this, 14), Ui.dp(this, 4));
        headerWrap.addView(Ui.topBar(this, "Zoe Chat", "Hybrid · Local LLM · Live Web · Multi-AI"));

        // Top Live Brain Mode Switcher (Hybrid Auto + Offline + Online + Web Grounding)
        HorizontalScrollView modeStrip = new HorizontalScrollView(this);
        modeStrip.setHorizontalScrollBarEnabled(false);
        LinearLayout modeRow = new LinearLayout(this);
        modeRow.setOrientation(LinearLayout.HORIZONTAL);
        modeRow.setGravity(Gravity.CENTER_VERTICAL);
        modeRow.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 4));

        modeAutoBtn = modeChip("⚡ Auto", v -> selectBrainMode(BrainMode.AUTO));
        modeAutoBtn.setId(R.id.conversation_mode_auto);
        modeLocalLlmBtn = modeChip("Zoe Local", v -> selectBrainMode(BrainMode.LOCAL_LLM));
        modeLocalLlmBtn.setId(R.id.conversation_mode_local_llm);
        webToggleBtn = modeChip("Web: off", v -> toggleWebSearch());
        webToggleBtn.setId(R.id.conversation_web_toggle);
        modeStemBtn = modeChip("Zoe Stem", v -> selectBrainMode(BrainMode.STEM));
        modeStemBtn.setId(R.id.conversation_mode_stem);
        modeCloudBtn = modeChip("Cloud AI", v -> selectBrainMode(BrainMode.CLOUD_AI));
        modeCloudBtn.setId(R.id.conversation_mode_cloud);
        modeLabBtn = modeChip("Lab Brain", v -> selectBrainMode(BrainMode.LAB_QWEN));
        modeLabBtn.setId(R.id.conversation_mode_lab);
        Button brainSettingsBtn = modeChip("⚙ Brain", v -> showBrainCouncilSheet());
        brainSettingsBtn.setId(R.id.conversation_brain_settings);
        Button threadsBtn = modeChip("Threads", v -> showThreadsSheet());
        threadsBtn.setId(R.id.conversation_threads_btn);
        Button newChatBtn = modeChip("+ New", v -> startNewThread());
        newChatBtn.setId(R.id.conversation_new_chat_btn);

        for (Button b : new Button[]{modeAutoBtn, modeLocalLlmBtn, webToggleBtn, modeStemBtn,
                modeCloudBtn, modeLabBtn, brainSettingsBtn, threadsBtn, newChatBtn}) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 40));
            lp.setMargins(0, 0, Ui.dp(this, 6), 0);
            modeRow.addView(b, lp);
        }
        modeStrip.addView(modeRow);
        headerWrap.addView(modeStrip);

        // Status + compact Caption / Voice row (keeps all Espresso IDs immediately accessible!)
        status = Ui.text(this, "⚡ Auto hybrid ready (offline-first · tap Web: off to enable live citations).", 13.5f, Ui.COBALT);
        status.setId(R.id.conversation_status);
        status.setPadding(Ui.dp(this, 4), Ui.dp(this, 2), Ui.dp(this, 4), Ui.dp(this, 4));
        headerWrap.addView(status);

        LinearLayout quickRow = new LinearLayout(this);
        quickRow.setOrientation(LinearLayout.HORIZONTAL);
        quickRow.setGravity(Gravity.CENTER_VERTICAL);
        captionToggle = Ui.button(this, "Caption mode: off", Ui.PINK, null);
        captionToggle.setId(R.id.conversation_captions);
        captionToggle.setOnClickListener(view -> {
            captionMode = !captionMode;
            captionToggle.setText(captionMode ? "Caption mode: on" : "Caption mode: off");
            status.setText(captionMode
                    ? "Caption mode on. Zoe stays silent and captions your speech."
                    : "Conversation mode on. Zoe speaks and responds.");
        });
        voicePicker = new Spinner(this);
        voicePicker.setId(R.id.conversation_voice);
        voicePicker.setContentDescription("Choose an installed English voice");
        voicePicker.setBackground(Ui.tonalPillDrawable(this, Ui.panelColor(this), Ui.primaryAccent(this), 16));
        LinearLayout.LayoutParams capLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f);
        capLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        quickRow.addView(captionToggle, capLp);
        quickRow.addView(voicePicker, new LinearLayout.LayoutParams(0, Ui.dp(this, 48), 1.0f));
        headerWrap.addView(quickRow);
        root.addView(headerWrap);

        // 2. Center Living Chat-Bubble Feed
        chatScroll = new ScrollView(this);
        chatScroll.setFillViewport(true);
        chatScroll.setBackgroundColor(Color.TRANSPARENT);
        LinearLayout scrollContent = Ui.vertical(this);
        scrollContent.setBackgroundColor(Color.TRANSPARENT);
        scrollContent.setPadding(Ui.dp(this, 14), Ui.dp(this, 6), Ui.dp(this, 14), Ui.dp(this, 12));

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
        osActionBar.addView(Ui.text(this, "APPROVAL-GATED PHONE ACTION PLAN · TAP TO RUN", 11.5f, Ui.CYAN));
        osActionBtn = Ui.primaryButton(this, "Open tool", Ui.COBALT, view -> {
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

        // 3. Thumb-Zone Next-Gen Composer Dock (Inline Look / Maps / Ask AI / Talk / Send)
        LinearLayout bottomDock = Ui.vertical(this);
        bottomDock.setBackgroundColor(Color.TRANSPARENT);
        bottomDock.setPadding(Ui.dp(this, 14), Ui.dp(this, 6), Ui.dp(this, 14), Ui.dp(this, 10));

        LinearLayout composer = new LinearLayout(this);
        composer.setOrientation(LinearLayout.HORIZONTAL);
        composer.setGravity(Gravity.CENTER_VERTICAL);
        composer.setBackground(Ui.cardBackground(this, 28));
        composer.setPadding(Ui.dp(this, 8), Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4));

        ImageView mapsBtn = Ui.iconActionButton(this, R.drawable.ic_zoe_location, Ui.textColor(this),
                Color.TRANSPARENT, "Open Maps and Safety",
                v -> startActivity(new Intent(this, LocationActivity.class)));
        composer.addView(mapsBtn, new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 44)));

        typedInput = Ui.input(this, "", "Ask Zoe anything…");
        typedInput.setId(R.id.conversation_input);
        typedInput.setBackgroundColor(Color.TRANSPARENT);
        typedInput.setPadding(Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10));
        composer.addView(typedInput, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));

        Button send = Ui.primaryButton(this, "Send", Ui.CYAN, view -> sendTypedMessage());
        send.setId(R.id.conversation_send);
        send.setMinHeight(Ui.dp(this, 46));
        send.setMinimumHeight(Ui.dp(this, 46));
        composer.addView(send, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout.LayoutParams compLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        compLp.setMargins(0, 0, 0, Ui.dp(this, 6));
        bottomDock.addView(composer, compLp);

        Button start = Ui.primaryButton(this, "Start talking", Ui.CYAN, view -> startConversation());
        start.setId(R.id.conversation_start);
        Button stop = Ui.button(this, "Stop", Ui.RUBY, view -> stopConversation());
        stop.setId(R.id.conversation_stop);
        Button askOtherBtn = Ui.button(this, "Ask AI ↗", Ui.GOLD, view -> showAskOtherAiDialog(
                typedInput.getText().toString().trim().isEmpty() ? lastUserPrompt() : typedInput.getText().toString().trim()));
        bottomDock.addView(Ui.buttonRow(this, start, stop, askOtherBtn));
        root.addView(bottomDock);

        setContentView(Ui.wrapWithBackdrop(this, root));
        Ui.configureEdgeToEdge(this, root);

        styleBrainModeStrip();
        renderChatFeed();

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
        b.setTextSize(13f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setMinHeight(Ui.dp(this, 40));
        b.setMinimumHeight(Ui.dp(this, 40));
        b.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        b.setStateListAnimator(null);
        b.setOnClickListener(listener);
        return b;
    }

    private void toggleWebSearch() {
        webSearchEnabled = !webSearchEnabled;
        styleBrainModeStrip();
        status.setText(webSearchEnabled
                ? "Live Web Grounding ON (zero-key DuckDuckGo + Wikipedia citations · HTTPS-only)."
                : "Live Web Grounding OFF (100% offline local mode).");
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
                    status.setText("⚡ Auto hybrid: Stem tools + live " + p.displayName + " streaming"
                            + (webSearchEnabled ? " + Web." : "."));
                } else if (model != null) {
                    status.setText("⚡ Auto hybrid: Stem tools + " + OnDeviceLlmEngine.modelLabelForFile(model)
                            + (webSearchEnabled ? " + Live Web." : " (offline)."));
                } else {
                    status.setText("⚡ Auto hybrid: Zoe Stem" + (webSearchEnabled ? " + Live Web." : " offline."));
                }
            }
            case STEM -> status.setText("Zoe Stem active (instant <5ms · Kloster A_0.08 + memory"
                    + (webSearchEnabled ? " + Live Web)." : " · 100% offline)."));
            case LOCAL_LLM -> {
                File model = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
                if (model != null) {
                    status.setText("On-Device Local LLM ready (" + OnDeviceLlmEngine.modelLabelForFile(model)
                            + (webSearchEnabled ? " + Live Web)." : " · 100% offline)."));
                } else {
                    status.setText("No Zoe Local model downloaded yet. Tap ⚙ Brain to download an offline neural pack (0.5B or 1.5B).");
                    showBrainCouncilSheet();
                }
            }
            case LAB_QWEN -> status.setText("Workstation Lab Brain mode (" + ElizaGemClient.savedEndpoint(this) + " · offline fallback).");
            case CLOUD_AI -> {
                MultiAiClient.Provider p = MultiAiClient.activeProvider(this);
                String key = MultiAiClient.savedKey(this, p);
                if (p != MultiAiClient.Provider.LOCAL_OPENAI && key.isEmpty()) {
                    status.setText("No " + p.displayName + " API key saved yet. Tap ⚙ Brain to add a key or switch provider.");
                } else {
                    status.setText("Online Streaming ready (" + p.displayName + " · " + MultiAiClient.savedModel(this, p)
                            + (webSearchEnabled ? " + Live Web)." : ")."));
                }
            }
        }
    }

    private void styleBrainModeStrip() {
        MultiAiClient.Provider activeCloud = MultiAiClient.activeProvider(this);
        modeCloudBtn.setText(activeCloud == MultiAiClient.Provider.LOCAL_OPENAI ? "Local API" : shortProviderName(activeCloud));
        webToggleBtn.setText(webSearchEnabled ? "Web: on" : "Web: off");
        styleChip(modeAutoBtn, brainMode == BrainMode.AUTO);
        styleChip(modeStemBtn, brainMode == BrainMode.STEM);
        styleChip(modeLocalLlmBtn, brainMode == BrainMode.LOCAL_LLM);
        styleChip(modeLabBtn, brainMode == BrainMode.LAB_QWEN);
        styleChip(modeCloudBtn, brainMode == BrainMode.CLOUD_AI);
        styleChip(webToggleBtn, webSearchEnabled);
    }

    private static String shortProviderName(MultiAiClient.Provider p) {
        return switch (p) {
            case GEMINI -> "Gemini";
            case CLAUDE -> "Claude";
            case CHATGPT -> "ChatGPT";
            case GROK -> "Grok";
            case LOCAL_OPENAI -> "Local API";
        };
    }

    private void styleChip(Button btn, boolean selected) {
        if (selected) {
            btn.setTextColor(Ui.isDark(this) ? Color.rgb(14, 15, 18) : Color.WHITE);
            btn.setBackground(Ui.tonalPillDrawable(this, Ui.primaryAccent(this), Ui.primaryAccent(this), 20));
        } else {
            btn.setTextColor(Ui.textColor(this));
            btn.setBackground(Ui.outlinedPillDrawable(this, Ui.panelColor(this), Ui.dividerColor(this), Ui.primaryAccent(this), 20));
        }
    }

    private void renderChatFeed() {
        chatFeed.removeAllViews();
        if (currentThread.messages.isEmpty()) {
            chatFeed.addView(buildWelcomeCanvas());
            return;
        }
        for (ChatHistoryStore.ChatMessage msg : currentThread.messages) {
            chatFeed.addView(buildMessageView(msg));
        }
        scrollChatToBottom();
    }

    private View buildWelcomeCanvas() {
        LinearLayout card = Ui.vertical(this);
        card.setGravity(Gravity.CENTER_HORIZONTAL);
        card.setPadding(Ui.dp(this, 16), Ui.dp(this, 22), Ui.dp(this, 16), Ui.dp(this, 18));

        ImageView gem = Ui.gemHomeButton(this, 50, () -> Ui.goHome(this));
        card.addView(gem, new LinearLayout.LayoutParams(Ui.dp(this, 58), Ui.dp(this, 58)));

        TextView hi = Ui.text(this, "Ask Zoe anything", 24f, Ui.TEXT);
        hi.setTypeface(Ui.SANS_MEDIUM);
        hi.setGravity(Gravity.CENTER);
        hi.setPadding(0, Ui.dp(this, 10), 0, Ui.dp(this, 4));
        Ui.applyGeminiGreetingShader(hi);
        card.addView(hi);

        TextView sub = Ui.text(this,
                "Offline Glass-Box Brain · Zoe Local Neural Engine · Multi-AI Council (Claude, Grok, ChatGPT, Gemini)",
                13.5f, Ui.MUTED);
        sub.setGravity(Gravity.CENTER);
        sub.setPadding(0, 0, 0, Ui.dp(this, 14));
        card.addView(sub);

        String[] starters = {
                "Who are you and how do you keep chats private?",
                "Explain Kloster's A_tau(p) equation simply",
                "Navigate to nearest hospital and set a 5 minute timer",
                "Tell me about L5 Phase 5"
        };
        for (String starter : starters) {
            Button chip = Ui.button(this, "✦ " + starter, Ui.COBALT, v -> {
                typedInput.setText(starter);
                sendTypedMessage();
            });
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
        String providerTitle = msg.provider.isEmpty() ? "ZOE" : msg.provider;
        if (msg.latencyMs > 0) {
            providerTitle += " · " + msg.latencyMs + " ms";
        }
        TextView hdrTxt = Ui.text(this, providerTitle, 12f, Ui.COBALT);
        hdrTxt.setTypeface(Ui.SANS_MEDIUM);
        hdrTxt.setPadding(Ui.dp(this, 8), 0, 0, 0);
        hdr.addView(hdrTxt);
        card.addView(hdr);

        TextView body = Ui.text(this, msg.text, 15.5f, Ui.TEXT);
        body.setTextIsSelectable(true);
        body.setPadding(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
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

            TextView glassToggle = Ui.text(this, "✦ Glass-Box Telemetry ▸", 12f, Ui.GOLD);
            glassToggle.setPadding(0, Ui.dp(this, 2), 0, Ui.dp(this, 6));
            glassToggle.setClickable(true);
            glassToggle.setFocusable(true);
            glassToggle.setOnClickListener(v -> {
                boolean open = glassDetails.getVisibility() != View.VISIBLE;
                glassDetails.setVisibility(open ? View.VISIBLE : View.GONE);
                glassToggle.setText(open ? "✦ Glass-Box Telemetry ▾" : "✦ Glass-Box Telemetry ▸");
            });
            card.addView(glassToggle);
            card.addView(glassDetails);
        }

        // Micro-Action Row (Speak / Copy / Ask Claude·Grok·GPT·Gemini)
        LinearLayout tools = new LinearLayout(this);
        tools.setOrientation(LinearLayout.HORIZONTAL);
        tools.setPadding(0, Ui.dp(this, 6), 0, 0);
        tools.addView(microChip("Speak", v -> speakReply(msg.text, "zoe-repeat")));
        tools.addView(microChip("Copy", v -> copyToClipboard(msg.text)));
        tools.addView(microChip("Ask Claude/Grok ↗", v -> showAskOtherAiDialog(lastUserPrompt())));
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
        chatScroll.post(() -> chatScroll.fullScroll(View.FOCUS_DOWN));
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
        status.setText("Started a fresh private conversation.");
    }

    private void sendTypedMessage() {
        String text = typedInput.getText() == null ? "" : typedInput.getText().toString().trim();
        if (text.isEmpty()) {
            return;
        }
        typedInput.setText("");
        processUserPrompt(text, false);
    }

    private void processUserPrompt(String text, boolean voiceTurn) {
        appendMessage(new ChatHistoryStore.ChatMessage("user", text, "YOU", "", 0));
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
        if (isMemoryCmd || isIdentityQuery || isActionCmd) {
            deliverLocalStem(text, "Zoe replied offline (0 cloud tokens · local stem).", voiceTurn);
            return;
        }

        // Smart Hybrid Auto-Router: picks Cloud (if key configured) -> Zoe Local (if installed) -> Web -> Stem
        BrainMode effectiveMode = brainMode;
        boolean autoRouted = false;
        if (brainMode == BrainMode.AUTO) {
            autoRouted = true;
            MultiAiClient.Provider activeCloud = MultiAiClient.activeProvider(this);
            boolean hasCloudKey = !MultiAiClient.savedKey(this, activeCloud).isEmpty();
            File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
            if (hasCloudKey) {
                effectiveMode = BrainMode.CLOUD_AI;
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
                    deliverLocalStem(text, "No Local LLM file installed yet — replied via Zoe Stem (tap ⚙ Brain to download).", voiceTurn);
                }
                return;
            }
            runOnDeviceLlm(modelFile, text, autoRouted, webSearchEnabled, voiceTurn);
            return;
        }

        if (effectiveMode == BrainMode.LAB_QWEN) {
            String endpoint = ElizaGemClient.savedEndpoint(this);
            status.setText("Asking Workstation Lab (" + endpoint + ")…");
            long t0 = System.currentTimeMillis();
            executor.execute(() -> {
                try {
                    ElizaGemClient.ChatReply res = studioClient.chat(endpoint, text, "gear2");
                    long dt = System.currentTimeMillis() - t0;
                    runOnUiThread(() -> {
                        if (isFinishing() || isDestroyed()) {
                            return;
                        }
                        String safeLabReply = OnDeviceLlmEngine.enforceZoeSovereignty(res.reply);
                        String glass = "Eliza-GEM Lab · gear=" + res.gearUsed + " · mode=" + res.mode
                                + " · A_tau=" + res.aTau + "/" + res.candidateCount;
                        deliverAssistantReply(safeLabReply, "LAB · " + res.gearUsed.toUpperCase(Locale.US), glass, dt,
                                "Lab Brain replied (" + res.gearUsed + ").", voiceTurn, null);
                    });
                } catch (Exception fallback) {
                    runOnUiThread(() -> {
                        if (!isFinishing() && !isDestroyed()) {
                            deliverLocalStem(text, "Lab unreachable — replied offline via Zoe Stem.", voiceTurn);
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
            deliverLocalStem(text, "No " + provider.displayName + " key saved — replied offline via Zoe Stem.", voiceTurn);
            return;
        }
        runCloudStreaming(provider, text, autoRouted, webSearchEnabled, voiceTurn);
    }

    private void runWebOnlyStem(String prompt, boolean autoRouted, boolean voiceTurn) {
        status.setText("Searching live public web sources (HTTPS · zero trackers)…");
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
                    deliverLocalStem(prompt, "No direct web summary found — replied offline via Zoe Stem.", voiceTurn);
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
        streamCard.addView(Ui.text(this, "✦ " + providerBadge + " · STREAMING ONLINE…", 12f, Ui.COBALT));
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
                            deliverLocalStem(prompt, provider.displayName + " unavailable (" + error.getMessage() + ") — offline fallback.", voiceTurn);
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
        streamCard.addView(Ui.text(this, "✦ " + label + (useWeb ? " · WEB-GROUNDED…" : " · STREAMING OFFLINE…"), 12f, Ui.GREEN));
        TextView streamBody = Ui.text(this, useWeb ? "Fetching live public sources & thinking locally…" : "Thinking locally…", 15.5f, Ui.TEXT);
        streamBody.setPadding(0, Ui.dp(this, 8), 0, 0);
        streamCard.addView(streamBody);
        chatFeed.addView(streamCard, lp);
        scrollChatToBottom();

        List<ChatHistoryStore.ChatMessage> historySnapshot = new ArrayList<>(currentThread.messages);
        String memCtx = buildMemorySummary();
        long t0 = System.currentTimeMillis();
        executor.execute(() -> {
            WebSearchClient.SearchResult webRes = useWeb ? WebSearchClient.search(prompt) : null;
            String webCtx = (webRes != null && webRes.hasSources()) ? webRes.formatContextForPrompt(700) : "";
            List<String> badges = (webRes != null && webRes.hasSources()) ? webRes.toSourceBadges() : null;
            String formatted = OnDeviceLlmEngine.buildChatMlPrompt(prompt, historySnapshot, memCtx, webCtx);
            try {
                String finalReply = localLlm.generateStreaming(modelFile, formatted, (partial, done) ->
                        runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed() && !partial.isEmpty()) {
                                streamBody.setText(partial);
                                scrollChatToBottom();
                            }
                        }));
                long dt = System.currentTimeMillis() - t0;
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        String clean = finalReply.isEmpty() ? "(No output generated.)" : finalReply;
                        boolean grounded = webRes != null && webRes.hasSources();
                        String cardTitle = grounded ? (label + " · WEB") : label;
                        String glass = (autoRouted ? "Auto-Router → " : "") + label
                                + " · On-Device MediaPipe GenAI · 0 cloud AI tokens"
                                + (grounded ? " · Live Web (" + webRes.sources.size() + " sources)" : "")
                                + " · " + dt + " ms";
                        deliverAssistantReply(clean, cardTitle, glass, dt,
                                grounded ? (label + " finished with " + webRes.sources.size() + " live web sources.")
                                        : (label + " finished offline (0 cloud tokens)."),
                                voiceTurn, badges);
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        deliverLocalStem(prompt, "Local LLM error (" + error.getMessage() + ") — offline Zoe Stem fallback.", voiceTurn);
                    }
                });
            }
        });
    }

    private void deliverLocalStem(String input, String statusNote, boolean voiceTurn) {
        long t0 = System.currentTimeMillis();
        ZoeBrainEngine.BrainReply res = brain.respond(input);
        long dt = Math.max(1L, System.currentTimeMillis() - t0);
        deliverAssistantReply(res.reply, "ZOE STEM · OFFLINE", res.telemetryBadge() + " · " + res.citation, dt, statusNote, voiceTurn, null);
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
        status.setText(statusNote);
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
            Button stepBtn = Ui.button(this, "Step " + (i + 1) + ": " + step.label, Ui.GREEN, v -> executeAction(step));
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
                    startActivity(new Intent(this, LocationActivity.class));
                    status.setText("Opened Maps & Safety.");
                }
                case OPEN_SAFETY -> {
                    PackageManager pm = getPackageManager();
                    Intent hub = pm.getLaunchIntentForPackage(OsToolsBridge.PIXEL_SAFETY_PACKAGE);
                    if (hub == null) {
                        hub = pm.getLaunchIntentForPackage(OsToolsBridge.ANDROID_EMERGENCY_PACKAGE);
                    }
                    startActivity(hub != null ? hub : new Intent(this, LocationActivity.class));
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

    // --- Zero-Key Native App Handoff (Claude, Grok, ChatGPT, Gemini, Share/Muse) ---

    private void showAskOtherAiDialog(String prompt) {
        String clean = prompt == null ? "" : prompt.trim();
        String[] choices = {
                "Claude (Prefill in Claude app)",
                "Grok (Send to Grok app)",
                "ChatGPT (Send to ChatGPT app)",
                "Gemini (Send to Gemini app)",
                "Run In-App Multi-AI Council (BYOK)",
                "Share to any app (incl. Meta Muse)"
        };
        new AlertDialog.Builder(this)
                .setTitle("Ask Another AI" + (clean.isEmpty() ? "" : " · \"" + ChatHistoryStore.titleFromPrompt(clean) + "\""))
                .setItems(choices, (d, which) -> {
                    switch (which) {
                        case 0 -> handoffToClaude(clean);
                        case 1 -> handoffToPackage(OsToolsBridge.GROK_PACKAGE, OsToolsBridge.grokWebUrl(), clean, "Grok");
                        case 2 -> handoffToPackage(OsToolsBridge.CHATGPT_PACKAGE, OsToolsBridge.chatGptWebUrl(), clean, "ChatGPT");
                        case 3 -> handoffToPackage(OsToolsBridge.GEMINI_PACKAGE, OsToolsBridge.geminiWebUrl(), clean, "Gemini");
                        case 4 -> runMultiAiCouncil(clean);
                        default -> sharePromptToAny(clean);
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void handoffToClaude(String prompt) {
        try {
            Intent deep = new Intent(Intent.ACTION_VIEW, Uri.parse(OsToolsBridge.claudeDeepLinkUri(prompt)));
            startActivity(deep);
            status.setText("Handed off prompt to Claude app.");
        } catch (ActivityNotFoundException fallback) {
            handoffToPackage(OsToolsBridge.CLAUDE_PACKAGE, OsToolsBridge.claudeWebUrl(prompt), prompt, "Claude");
        }
    }

    private void handoffToPackage(String pkg, String webFallback, String prompt, String name) {
        if (!prompt.isEmpty()) {
            Intent send = new Intent(Intent.ACTION_SEND)
                    .setType("text/plain")
                    .setPackage(pkg)
                    .putExtra(Intent.EXTRA_TEXT, prompt);
            try {
                startActivity(send);
                status.setText("Sent prompt directly to " + name + " app.");
                return;
            } catch (ActivityNotFoundException ignored) {
            }
        }
        Intent launch = getPackageManager().getLaunchIntentForPackage(pkg);
        if (launch != null) {
            startActivity(launch);
            status.setText("Opened " + name + " app.");
            return;
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(webFallback)));
            status.setText("Opened " + name + " in browser.");
        } catch (ActivityNotFoundException error) {
            status.setText(name + " is not installed on this device.");
        }
    }

    private void sharePromptToAny(String prompt) {
        String body = prompt.isEmpty() ? lastResponse : prompt;
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TEXT, body);
        startActivity(Intent.createChooser(share, "Send to AI app"));
    }

    private void runMultiAiCouncil(String prompt) {
        if (prompt.isEmpty()) {
            status.setText("Type a question first, then tap Ask AI -> Run Multi-AI Council.");
            return;
        }
        List<MultiAiClient.Provider> configured = MultiAiClient.configuredCloudProviders(this);
        if (configured.isEmpty()) {
            status.setText("Add 1+ API keys in ⚙ Brain (Gemini, Claude, ChatGPT, or Grok) to run In-App Council.");
            showBrainCouncilSheet();
            return;
        }
        status.setText("Consulting AI Council (" + configured.size() + " cloud + Zoe Stem)…");
        executor.execute(() -> {
            List<String> texts = new ArrayList<>();
            StringBuilder combined = new StringBuilder();
            ZoeBrainEngine.BrainReply stem = brain.respond(prompt);
            texts.add(stem.reply);
            combined.append("[ZOE OFFLINE STEM]\n").append(stem.reply).append("\n\n");
            for (MultiAiClient.Provider p : configured) {
                try {
                    String ans = MultiAiClient.ask(this, p, prompt, "");
                    texts.add(ans);
                    combined.append("[").append(p.displayName.toUpperCase(Locale.US)).append("]\n")
                            .append(ans).append("\n\n");
                } catch (Exception err) {
                    combined.append("[").append(p.displayName.toUpperCase(Locale.US))
                            .append(" · UNAVAILABLE] ").append(err.getMessage()).append("\n\n");
                }
            }
            double agreement = MultiAiClient.computeAgreementScore(texts);
            String glass = String.format(Locale.US,
                    "AI Council (%d voices) · Lexical Agreement=%.0f%% · Honesty: independent answers shown side-by-side",
                    texts.size(), agreement * 100.0);
            runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed()) {
                    deliverAssistantReply(combined.toString().trim(), "ZOE AI COUNCIL", glass, 0,
                            String.format(Locale.US, "AI Council replied (agreement %.0f%%).", agreement * 100.0), false);
                }
            });
        });
    }

    // --- Brain, On-Device LLM Downloader & Multi-Provider Settings Sheet ---

    private void showBrainCouncilSheet() {
        ScrollView sv = new ScrollView(this);
        LinearLayout box = Ui.vertical(this);
        box.setBackground(Ui.cardBackground(this, 26));
        box.setPadding(Ui.dp(this, 18), Ui.dp(this, 18), Ui.dp(this, 18), Ui.dp(this, 18));

        TextView heading = Ui.text(this, "Zoe Brain, Local LLM & AI Council", 19f, Ui.TEXT);
        heading.setTypeface(Ui.SANS_MEDIUM);
        box.addView(heading);

        // Section A: On-Device Offline Neural LLM (MediaPipe GenAI)
        box.addView(Ui.text(this, "1. ON-DEVICE OFFLINE NEURAL LLM (0 CLOUD TOKENS)", 12f, Ui.GREEN));
        TextView llmStatus = Ui.text(this, localLlmStatusSummary(), 13.5f, Ui.MUTED);
        box.addView(llmStatus);

        for (OnDeviceLlmEngine.ModelSpec spec : OnDeviceLlmEngine.ModelSpec.values()) {
            boolean installed = OnDeviceLlmEngine.isInstalled(this, spec);
            String label = (installed ? "✓ Use " : "⬇ Download ") + spec.label;
            Button mBtn = Ui.button(this, label, installed ? Ui.GREEN : Ui.COBALT, v -> {
                OnDeviceLlmEngine.saveSelectedModel(this, spec);
                if (OnDeviceLlmEngine.isInstalled(this, spec)) {
                    brainMode = BrainMode.LOCAL_LLM;
                    styleBrainModeStrip();
                    llmStatus.setText("Selected installed model: " + spec.label);
                    status.setText("Local LLM selected: " + spec.label + " (100% offline).");
                } else {
                    llmStatus.setText("Downloading " + spec.label + " from Hugging Face LiteRT… 0%");
                    v.setEnabled(false);
                    executor.execute(() -> {
                        try {
                            localLlm.downloadModel(spec, (pct, dlMb, totMb) -> runOnUiThread(() ->
                                    llmStatus.setText("Downloading " + spec.id + ": " + pct + "% (" + dlMb + "/" + totMb + " MB)")));
                            runOnUiThread(() -> {
                                if (!isFinishing() && !isDestroyed()) {
                                    brainMode = BrainMode.LOCAL_LLM;
                                    styleBrainModeStrip();
                                    llmStatus.setText("✓ Installed offline: " + spec.label + "! Ready in Local LLM mode.");
                                    status.setText("Local LLM installed (" + spec.id + "). Zero cloud needed!");
                                    ((Button) v).setText("✓ Use " + spec.label);
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

        // Section B: Optional Multi-Provider Cloud BYOK Keys (Gemini / Claude / ChatGPT / Grok / Local OpenAI)
        box.addView(Ui.text(this, "\n2. CLOUD AI & WORKSTATION KEYS (OPTIONAL BYOK)", 12f, Ui.COBALT));
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

        EditText keyField = Ui.input(this, MultiAiClient.savedKey(this, currentProv), "Optional API key (stays private on device)");
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

        Button saveProviderBtn = Ui.primaryButton(this, "Save & Activate Cloud Provider", Ui.COBALT, v -> {
            MultiAiClient.Provider chosen = allProviders[providerSpinner.getSelectedItemPosition()];
            MultiAiClient.saveActiveProvider(this, chosen);
            MultiAiClient.saveKey(this, chosen, keyField.getText().toString());
            MultiAiClient.saveModel(this, chosen, modelField.getText().toString());
            brainMode = BrainMode.CLOUD_AI;
            styleBrainModeStrip();
            status.setText("Saved " + chosen.displayName + " (" + MultiAiClient.savedModel(this, chosen) + ").");
        });
        box.addView(saveProviderBtn);

        // Section C: Zoe Voice, Sing Zoe & Memory Sync
        box.addView(Ui.text(this, "\n3. ZOE NATIVE VOICE & LAB MEMORY", 12f, Ui.RUBY));
        Button voiceToggle = Ui.button(this, useNativeVoice ? "Voice: Zoe Synth (44.1 kHz)" : "Voice: OS TTS", Ui.COBALT, v -> {
            useNativeVoice = !useNativeVoice;
            ((Button) v).setText(useNativeVoice ? "Voice: Zoe Synth (44.1 kHz)" : "Voice: OS TTS");
            status.setText(useNativeVoice ? "Zoe Native Formant Voice active." : "OS text-to-speech active.");
        });
        Button singBtn = Ui.button(this, "Sing Zoe", Ui.RUBY, v -> playZoeSong());
        box.addView(Ui.buttonRow(this, voiceToggle, singBtn));

        Button syncMemBtn = Ui.button(this, "Sync memory to Lab", Ui.GOLD, v -> syncMemoryToLab());
        Button exportBtn = Ui.button(this, "Share transcript", Ui.CYAN, v -> shareTranscript());
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
                    + " (" + (installed.length() / (1024L * 1024L)) + " MB).";
        }
        return "No Zoe Local neural pack downloaded yet. Pick 0.5B Compact (fast) or 1.5B Pro (recommended) below.";
    }

    private void showThreadsSheet() {
        String[] labels = new String[threads.size()];
        for (int i = 0; i < threads.size(); i++) {
            ChatHistoryStore.ChatThread t = threads.get(i);
            labels[i] = t.title + " (" + t.messages.size() + " msgs · " + t.updatedIso + ")";
        }
        new AlertDialog.Builder(this)
                .setTitle("Private Conversations (" + threads.size() + ")")
                .setItems(labels, (d, which) -> {
                    currentThread = threads.get(which);
                    renderChatFeed();
                    status.setText("Opened conversation: " + currentThread.title);
                })
                .setPositiveButton("+ New chat", (d, w) -> startNewThread())
                .setNeutralButton("Clear current", (d, w) -> {
                    currentThread.messages.clear();
                    ChatHistoryStore.save(this, threads);
                    renderChatFeed();
                    status.setText("Cleared messages in current thread.");
                })
                .setNegativeButton("Close", null)
                .show();
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
        voices.sort(Comparator.comparing(Voice::getName));
        List<String> names = new ArrayList<>();
        if (voices.isEmpty()) {
            names.add("System default voice");
        } else {
            for (Voice v : voices) {
                names.add(v.getLocale().toLanguageTag() + " · " + v.getName());
            }
        }
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, names);
        voicePicker.setAdapter(adapter);
        voicePicker.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int pos, long id) {
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
        status.setText("Conversation stopped. The microphone is off.");
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
