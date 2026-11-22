package research.zoetic.zoe;

import android.Manifest;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ConversationActivity extends ComponentActivity {
    private static final int MICROPHONE_PERMISSION = 73;
    private final ArrayList<String> exchanges = new ArrayList<>();
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final ElizaGemClient studioClient = new ElizaGemClient();
    private ZoeBrainEngine brain;
    private ZoeNativeVoice nativeVoice;
    private TextView status;
    private TextView brainBadge;
    private TextView transcript;
    private EditText typedInput;
    private Button cloudToggle;
    private Button nativeVoiceToggle;
    private Button labBridgeToggle;
    private TextToSpeech textToSpeech;
    private SpeechRecognizer recognizer;
    private Spinner voicePicker;
    private final List<Voice> voices = new ArrayList<>();
    private boolean ttsReady;
    private boolean startWhenReady;
    private boolean active;
    private boolean captionMode;
    private boolean cloudChatMode;
    private boolean useNativeVoice;
    private boolean useLabStudio;
    private String lastResponse = "Hi, I'm Zoe. What would you like to explore?";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        brain = new ZoeBrainEngine(this);
        nativeVoice = new ZoeNativeVoice();
        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(android.graphics.Color.TRANSPARENT);

        // Top calm header + quick mode controls
        LinearLayout headerWrap = Ui.vertical(this);
        headerWrap.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        headerWrap.setPadding(Ui.dp(this, 16), Ui.dp(this, 6), Ui.dp(this, 16), Ui.dp(this, 6));
        headerWrap.addView(Ui.topBar(this, "Talk with Zoe", "Private on-device voice & chat"));

        status = Ui.text(this, "Conversation is off. Start whenever you are ready.", 14f, Ui.COBALT);
        status.setId(R.id.conversation_status);
        status.setPadding(Ui.dp(this, 4), 0, Ui.dp(this, 4), Ui.dp(this, 8));
        headerWrap.addView(status);

        Button captionToggle = Ui.button(this, "Caption mode: off", Ui.PINK, null);
        captionToggle.setId(R.id.conversation_captions);
        captionToggle.setOnClickListener(view -> {
            captionMode = !captionMode;
            captionToggle.setText(captionMode ? "Caption mode: on" : "Caption mode: off");
            status.setText(captionMode ? "Caption mode on. Zoe stays silent and captions your speech." : "Conversation mode on. Zoe speaks and responds.");
        });
        cloudToggle = Ui.button(this, "Cloud chat: off", Ui.GOLD, view -> {
            cloudChatMode = !cloudChatMode;
            cloudToggle.setText(cloudChatMode ? "Cloud chat: on" : "Cloud chat: off");
            status.setText(cloudChatMode
                    ? "Cloud chat enabled (requires saved Gemini key; falls back cleanly otherwise)."
                    : "Cloud chat off. Local deterministic responses active.");
        });
        cloudToggle.setId(R.id.conversation_cloud_toggle);
        headerWrap.addView(Ui.buttonRow(this, captionToggle, cloudToggle));

        voicePicker = new Spinner(this);
        voicePicker.setId(R.id.conversation_voice);
        voicePicker.setContentDescription("Choose an installed English voice");
        voicePicker.setBackground(Ui.tonalPillDrawable(this, Ui.panelColor(this), Ui.primaryAccent(this), 18));
        LinearLayout.LayoutParams voiceParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        voiceParams.setMargins(Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 2));
        headerWrap.addView(voicePicker, voiceParams);
        root.addView(headerWrap);

        // Center spacious Gemini conversation feed
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        LinearLayout feed = Ui.vertical(this);
        feed.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        feed.setPadding(Ui.dp(this, 16), Ui.dp(this, 8), Ui.dp(this, 16), Ui.dp(this, 12));

        LinearLayout welcomeRow = new LinearLayout(this);
        welcomeRow.setOrientation(LinearLayout.HORIZONTAL);
        welcomeRow.setGravity(android.view.Gravity.CENTER_VERTICAL);
        welcomeRow.setPadding(Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 10));
        welcomeRow.addView(Ui.gemHomeButton(this, 30, () -> Ui.goHome(this)),
                new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));
        brainBadge = Ui.text(this,
                "Zoe Brain · gear1_mobile · mem=" + brain.memoryCount() + " · Offline",
                13.5f, Ui.MUTED);
        brainBadge.setPadding(Ui.dp(this, 10), 0, 0, 0);
        welcomeRow.addView(brainBadge);
        feed.addView(welcomeRow);

        transcript = Ui.text(this, "No turns yet. Try typing `remember ...`, asking about L5 Phase 4, or tapping Start talking.", 16f, Ui.TEXT);
        transcript.setBackground(Ui.cardBackground(this, 24));
        transcript.setPadding(Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 20), Ui.dp(this, 18));
        transcript.setTextIsSelectable(true);
        feed.addView(transcript);

        LinearLayout moreDrawer = Ui.vertical(this);
        moreDrawer.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        moreDrawer.setVisibility(android.view.View.GONE);

        nativeVoiceToggle = Ui.button(this, "Voice: OS TTS", Ui.COBALT, view -> {
            useNativeVoice = !useNativeVoice;
            nativeVoiceToggle.setText(useNativeVoice ? "Voice: Zoe Synth" : "Voice: OS TTS");
            status.setText(useNativeVoice
                    ? "Zoe Native Formant Voice active (44.1 kHz DSP; uses Lab 3D WAV when connected)."
                    : "Device OS text-to-speech voice active.");
        });
        labBridgeToggle = Ui.button(this, "Lab Brain: off", Ui.GREEN, view -> {
            useLabStudio = !useLabStudio;
            labBridgeToggle.setText(useLabStudio ? "Lab Brain: on" : "Lab Brain: off");
            status.setText(useLabStudio
                    ? "Workstation Lab Brain enabled (routes to Eliza-GEM / Qwen2.5-3B; falls back offline cleanly)."
                    : "On-device Zoe Glass-Box Brain active (100% offline).");
        });
        moreDrawer.addView(Ui.buttonRow(this, nativeVoiceToggle, labBridgeToggle));

        moreDrawer.addView(Ui.buttonRow(this,
                Ui.button(this, "Sing Zoe", Ui.RUBY, view -> playZoeSong()),
                Ui.button(this, "Sync memory to Lab", Ui.GOLD, view -> syncMemoryToLab())));

        moreDrawer.addView(Ui.buttonRow(this,
                Ui.button(this, "Repeat", Ui.GREEN, view -> speakReply(lastResponse, "zoe-repeat")),
                Ui.button(this, "Open Gemini", Ui.GOLD, view -> openGemini())));
        moreDrawer.addView(Ui.buttonRow(this,
                Ui.button(this, "Clear transcript", Ui.MUTED, view -> {
                    exchanges.clear();
                    updateTranscript();
                }),
                Ui.button(this, "Share transcript", Ui.CYAN, view -> shareTranscript())));

        Button moreToggle = Ui.disclosureButton(this, "More actions ▾", null);
        moreToggle.setOnClickListener(view -> {
            boolean open = moreDrawer.getVisibility() != android.view.View.VISIBLE;
            moreDrawer.setVisibility(open ? android.view.View.VISIBLE : android.view.View.GONE);
            moreToggle.setText(open ? "More actions ▴" : "More actions ▾");
        });
        feed.addView(moreToggle);
        feed.addView(moreDrawer);
        scroll.addView(feed);
        root.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f));

        // Bottom thumb-zone Google Gemini Composer & Voice Dock
        LinearLayout bottomDock = Ui.vertical(this);
        bottomDock.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        bottomDock.setPadding(Ui.dp(this, 16), Ui.dp(this, 6), Ui.dp(this, 16), Ui.dp(this, 12));

        LinearLayout composer = new LinearLayout(this);
        composer.setOrientation(LinearLayout.HORIZONTAL);
        composer.setGravity(android.view.Gravity.CENTER_VERTICAL);
        composer.setBackground(Ui.cardBackground(this, 28));
        composer.setPadding(Ui.dp(this, 10), Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6));

        typedInput = Ui.input(this, "", "Message Zoe…");
        typedInput.setId(R.id.conversation_input);
        typedInput.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        typedInput.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10));
        composer.addView(typedInput, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f));

        Button send = Ui.primaryButton(this, "Send", Ui.CYAN, view -> sendTypedMessage());
        send.setId(R.id.conversation_send);
        send.setMinHeight(Ui.dp(this, 48));
        send.setMinimumHeight(Ui.dp(this, 48));
        composer.addView(send, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        LinearLayout.LayoutParams compLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        compLp.setMargins(0, 0, 0, Ui.dp(this, 8));
        bottomDock.addView(composer, compLp);

        Button start = Ui.primaryButton(this, "Start talking", Ui.CYAN, view -> startConversation());
        start.setId(R.id.conversation_start);
        Button stop = Ui.button(this, "Stop", Ui.RUBY, view -> stopConversation());
        stop.setId(R.id.conversation_stop);
        bottomDock.addView(Ui.buttonRow(this, start, stop));
        root.addView(bottomDock);

        setContentView(Ui.wrapWithBackdrop(this, root));
        Ui.configureEdgeToEdge(this, root);

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
            } else {
                status.setText("Text to speech could not start. You can still read and type here or in the other Zoe panels.");
            }
        }));
    }

    private void loadVoices() {
        voices.clear();
        if (textToSpeech == null) {
            return;
        }
        Set<Voice> available = null;
        try {
            available = textToSpeech.getVoices();
        } catch (RuntimeException ignored) {
        }
        if (available != null) {
            for (Voice voice : available) {
                if (voice != null && voice.getLocale() != null && "en".equals(voice.getLocale().getLanguage())) {
                    voices.add(voice);
                }
            }
        }
        voices.sort(Comparator.comparing(voice -> voice.getLocale().toString() + " · " + voice.getName()));
        List<String> labels = new ArrayList<>();
        for (Voice voice : voices) {
            labels.add(voice.getLocale() + " · " + voice.getName());
        }
        if (labels.isEmpty()) {
            labels.add("Default English voice");
        }
        voicePicker.setAdapter(Ui.spinnerAdapter(this, labels));
        Voice defaultVoice = null;
        try {
            defaultVoice = textToSpeech.getDefaultVoice();
        } catch (RuntimeException ignored) {
        }
        String fallbackName = defaultVoice == null ? "" : defaultVoice.getName();
        String saved = getPreferences(MODE_PRIVATE).getString("voice_name", fallbackName);
        for (int index = 0; index < voices.size(); index++) {
            if (voices.get(index).getName().equals(saved)) {
                voicePicker.setSelection(index);
                textToSpeech.setVoice(voices.get(index));
                break;
            }
        }
        voicePicker.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, android.view.View view, int position, long id) {
                if (position >= 0 && position < voices.size() && textToSpeech != null) {
                    textToSpeech.setVoice(voices.get(position));
                    getPreferences(MODE_PRIVATE).edit().putString("voice_name", voices.get(position).getName()).apply();
                }
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
            }
        });
    }

    private void sendTypedMessage() {
        String text = typedInput.getText().toString().trim();
        if (text.isEmpty()) {
            return;
        }
        typedInput.setText("");
        addExchange("YOU", text);
        if (useLabStudio) {
            String endpoint = ElizaGemClient.savedEndpoint(this);
            status.setText("Routing through Workstation Lab Brain (" + endpoint + ")…");
            executor.execute(() -> {
                try {
                    ElizaGemClient.ChatReply lab = studioClient.chat(endpoint, text, "gear2");
                    runOnUiThread(() -> {
                        if (isFinishing() || isDestroyed()) {
                            return;
                        }
                        lastResponse = lab.reply;
                        brainBadge.setText(String.format(Locale.US,
                                "Lab %s · %s · A_%.2f=%d/%d",
                                lab.gearUsed, lab.mode, lab.tau, lab.aTau, lab.candidateCount));
                        addExchange("ZOE LAB [" + lab.gearUsed.toUpperCase(Locale.US) + "]", lab.reply);
                        status.setText("Workstation Lab Brain replied (" + lab.latencyMs + " ms).");
                        if (!captionMode) {
                            speakReply(lab.reply, "zoe-typed");
                        }
                    });
                } catch (Exception error) {
                    runOnUiThread(() -> {
                        if (!isFinishing() && !isDestroyed()) {
                            deliverLocalBrainReply(text, "Lab offline — replied via on-device Zoe Brain.");
                        }
                    });
                }
            });
            return;
        }
        if (cloudChatMode) {
            String key = CloudVisionClient.savedApiKey(this);
            if (!key.isEmpty()) {
                String model = CloudVisionClient.savedModel(this);
                status.setText("Asking Cloud (" + model + ") via " + Ui.networkStatusLabel(this) + "…");
                executor.execute(() -> {
                    try {
                        String reply = "[ONLINE CLOUD · GEMINI] " + CloudVisionClient.askText(key, model, text);
                        runOnUiThread(() -> {
                            if (isFinishing() || isDestroyed()) {
                                return;
                            }
                            lastResponse = reply;
                            brainBadge.setText("Cloud Gemini · " + model);
                            addExchange("CLOUD", reply);
                            status.setText("Cloud reply received.");
                            if (!captionMode) {
                                speakReply(reply, "zoe-typed");
                            }
                        });
                    } catch (Exception error) {
                        runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed()) {
                                deliverLocalBrainReply(text, "Cloud failed (" + error.getMessage() + "); replied locally.");
                            }
                        });
                    }
                });
                return;
            }
        }
        deliverLocalBrainReply(text, "Zoe Brain replied offline (0 cloud tokens).");
    }

    private void deliverLocalBrainReply(String input, String statusNote) {
        ZoeBrainEngine.BrainReply res = brain.respond(input);
        lastResponse = res.reply;
        brainBadge.setText(res.telemetryBadge());
        addExchange("ZOE", res.reply);
        status.setText(statusNote);
        if (!captionMode) {
            speakReply(res.reply, "zoe-typed");
        }
    }

    private void speakReply(String text, String utteranceId) {
        if (text == null || text.isBlank()) {
            return;
        }
        if (useNativeVoice) {
            if (useLabStudio) {
                String endpoint = ElizaGemClient.savedEndpoint(this);
                executor.execute(() -> {
                    try {
                        byte[] wav = studioClient.fetchSpeakWav(endpoint, text, "speak");
                        nativeVoice.playWavBytes(wav, () -> onNativeSpeechFinished(utteranceId));
                    } catch (Exception fallback) {
                        nativeVoice.speak(text, () -> onNativeSpeechFinished(utteranceId));
                    }
                });
            } else {
                nativeVoice.speak(text, () -> onNativeSpeechFinished(utteranceId));
            }
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
        if (useLabStudio) {
            String endpoint = ElizaGemClient.savedEndpoint(this);
            executor.execute(() -> {
                try {
                    byte[] wav = studioClient.fetchSpeakWav(endpoint, "zoe", "sing");
                    nativeVoice.playWavBytes(wav, null);
                } catch (Exception fallback) {
                    nativeVoice.singZoe(null);
                }
            });
        } else {
            nativeVoice.singZoe(null);
        }
    }

    private void syncMemoryToLab() {
        List<ZoeBrainEngine.MemoryNote> notes = brain.notesSnapshot();
        if (notes.isEmpty()) {
            status.setText("No local notes to sync yet. Type `remember ...` or `relay ...` first.");
            return;
        }
        String endpoint = ElizaGemClient.savedEndpoint(this);
        status.setText("Syncing " + notes.size() + " private notes to " + endpoint + "…");
        executor.execute(() -> {
            try {
                ElizaGemClient.SyncResult res = studioClient.syncMemory(endpoint, android.os.Build.MODEL, notes);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Unified memory synced: " + res.accepted + " added, "
                                + res.deduplicated + " already synced (chain "
                                + (res.chainHead.length() > 10 ? res.chainHead.substring(0, 10) : res.chainHead) + ").");
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
                    addExchange("CAPTION", heard);
                    startListening();
                    return;
                }
                addExchange("YOU", heard);
                if (ConversationResponse.isStop(heard)) {
                    String goodbye = ConversationResponse.forInput(heard);
                    addExchange("ZOE", goodbye);
                    active = false;
                    status.setText("Conversation stopped. The microphone is off.");
                    if (ttsReady && textToSpeech != null) {
                        textToSpeech.speak(goodbye, TextToSpeech.QUEUE_FLUSH, null, "zoe-goodbye");
                    }
                    return;
                }
                if (cloudChatMode) {
                    String key = CloudVisionClient.savedApiKey(ConversationActivity.this);
                    if (!key.isEmpty()) {
                        String model = CloudVisionClient.savedModel(ConversationActivity.this);
                        status.setText("Asking Cloud (" + model + ") via " + Ui.networkStatusLabel(ConversationActivity.this) + "…");
                        executor.execute(() -> {
                            try {
                                String reply = "[ONLINE CLOUD · GEMINI] " + CloudVisionClient.askText(key, model, heard);
                                runOnUiThread(() -> {
                                    if (isFinishing() || isDestroyed() || !active) {
                                        return;
                                    }
                                    addExchange("CLOUD", reply);
                                    speakThenListen(reply);
                                });
                            } catch (Exception error) {
                                runOnUiThread(() -> {
                                    if (isFinishing() || isDestroyed() || !active) {
                                        return;
                                    }
                                    String fallback = ConversationResponse.forInput(heard);
                                    addExchange("ZOE (OFFLINE FALLBACK)", fallback);
                                    speakThenListen(fallback);
                                });
                            }
                        });
                        return;
                    }
                }
                ZoeBrainEngine.BrainReply local = brain.respond(heard);
                brainBadge.setText(local.telemetryBadge());
                addExchange("ZOE", local.reply);
                speakThenListen(local.reply);
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
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission issue (code 9). No command was executed.";
            case SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT ->
                    "Speech network error (code " + error + "). No command was executed.";
            case SpeechRecognizer.ERROR_NO_MATCH -> "No speech match heard (code 7). Tap again whenever ready.";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Speech recognizer is busy (code 8). Wait a moment and try again.";
            case SpeechRecognizer.ERROR_SERVER -> "Speech recognition service error (code 4). No command was executed.";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech heard before timeout (code 6). Tap again whenever ready.";
            case 12, 13 -> "On-device speech language model busy or unavailable (code " + error + "). No command was executed.";
            default -> "Speech recognition ended (code " + error + "). No command was executed.";
        };
    }

    private void addExchange(String role, String text) {
        exchanges.add(role + " · " + text);
        if (exchanges.size() > 12) {
            exchanges.remove(0);
        }
        updateTranscript();
    }

    private void updateTranscript() {
        transcript.setText(exchanges.isEmpty()
                ? "No turns yet. Transcripts stay on this screen unless you clear or share them."
                : String.join("\n\n", exchanges));
    }

    private void stopConversation() {
        active = false;
        startWhenReady = false;
        if (recognizer != null) {
            recognizer.cancel();
        }
        if (textToSpeech != null) {
            textToSpeech.stop();
        }
        if (nativeVoice != null) {
            nativeVoice.stop();
        }
        status.setText("Conversation stopped. The microphone is off.");
    }

    private void shareTranscript() {
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_SUBJECT, "Zoe conversation")
                .putExtra(Intent.EXTRA_TEXT, transcript.getText().toString());
        try {
            startActivity(Intent.createChooser(share, "Share transcript"));
        } catch (ActivityNotFoundException error) {
            status.setText("No sharing app is available.");
        }
    }

    private void openGemini() {
        stopConversation();
        try {
            Intent launch = getPackageManager().getLaunchIntentForPackage("com.google.android.apps.bard");
            if (launch == null) {
                launch = new Intent(Intent.ACTION_VIEW, Uri.parse("https://gemini.google.com"));
            }
            startActivity(launch);
        } catch (ActivityNotFoundException error) {
            status.setText("No Gemini app or web browser is available.");
        }
    }

    private void destroyRecognizer() {
        if (recognizer != null) {
            recognizer.destroy();
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
                status.setText("Microphone permission was not granted. No audio was captured.");
            }
        }
    }

    @Override
    protected void onPause() {
        stopConversation();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        active = false;
        destroyRecognizer();
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
        }
        if (nativeVoice != null) {
            nativeVoice.close();
        }
        executor.shutdownNow();
        super.onDestroy();
    }
}
