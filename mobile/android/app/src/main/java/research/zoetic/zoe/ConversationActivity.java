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
import android.widget.Button;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.ArrayList;
import java.util.Locale;

public final class ConversationActivity extends ComponentActivity {
    private static final int MICROPHONE_PERMISSION = 73;
    private final ArrayList<String> exchanges = new ArrayList<>();
    private TextView status;
    private TextView transcript;
    private TextToSpeech textToSpeech;
    private SpeechRecognizer recognizer;
    private android.widget.Spinner voicePicker;
    private final java.util.List<android.speech.tts.Voice> voices = new ArrayList<>();
    private boolean ttsReady;
    private boolean startWhenReady;
    private boolean active;
    private boolean captionMode;
    private String lastResponse = "Hi, I'm Zoe. What would you like to explore?";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        android.widget.LinearLayout content = Ui.vertical(this);
        content.setPadding(Ui.dp(this, 18), Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(scroll);
        content.addView(Ui.heading(this, "Talk with Zoe"));
        content.addView(Ui.text(this,
                "Zoe speaks, you answer, Zoe responds. Turns repeat until Stop. The microphone is off when you leave this screen.",
                16, Ui.MUTED));
        status = Ui.text(this, "Conversation is off. Start whenever you are ready.", 16, Ui.YELLOW);
        status.setId(R.id.conversation_status);
        content.addView(status);
        voicePicker = new android.widget.Spinner(this);
        voicePicker.setId(R.id.conversation_voice);
        voicePicker.setContentDescription("Choose an installed English voice");
        content.addView(voicePicker);
        Button start = Ui.button(this, "Start talking", view -> startConversation());
        start.setId(R.id.conversation_start);
        Button stop = Ui.button(this, "Stop", view -> stopConversation());
        stop.setId(R.id.conversation_stop);
        content.addView(Ui.buttonRow(this, start, stop));
        Button captionToggle = Ui.button(this, "Caption mode: off", null);
        captionToggle.setId(R.id.conversation_captions);
        captionToggle.setOnClickListener(view -> {
            captionMode = !captionMode;
            captionToggle.setText(captionMode ? "Caption mode: on" : "Caption mode: off");
            status.setText(captionMode ? "Caption mode on. Zoe stays silent and captions your speech." : "Conversation mode on. Zoe speaks and responds.");
        });
        content.addView(captionToggle);
        content.addView(Ui.buttonRow(this,
                Ui.button(this, "Repeat", view -> {
                    if (ttsReady) {
                        textToSpeech.speak(lastResponse, TextToSpeech.QUEUE_FLUSH, null, "zoe-repeat");
                    }
                }),
                Ui.button(this, "Open Gemini", view -> openGemini())));
        content.addView(Ui.button(this, "Clear transcript", view -> {
            exchanges.clear();
            updateTranscript();
        }));
        transcript = Ui.text(this, "No turns yet. Transcripts stay on this screen unless you clear or share them.", 17, Ui.TEXT);
        transcript.setBackground(Ui.panelBackground(this, Ui.CYAN, 16));
        transcript.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        transcript.setTextIsSelectable(true);
        content.addView(transcript);
        content.addView(Ui.button(this, "Share transcript", view -> shareTranscript()));
        content.addView(Ui.text(this,
                "Local replies are deterministic for camera, volume, battery, multi-view, and Gemini navigation. Open-ended understanding is not faked.",
                13, Ui.MUTED));
        textToSpeech = new TextToSpeech(this, result -> {
            ttsReady = result == TextToSpeech.SUCCESS;
            if (ttsReady) {
                textToSpeech.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override
                    public void onStart(String utteranceId) {
                    }

                    @Override
                    public void onDone(String utteranceId) {
                        if (active && "zoe-turn".equals(utteranceId)) {
                            startListening();
                        }
                    }

                    @Override
                    public void onError(String utteranceId) {
                        if (active && "zoe-turn".equals(utteranceId)) {
                            startListening();
                        }
                    }
                });
                loadVoices();
                if (startWhenReady) {
                    startWhenReady = false;
                    speakThenListen(lastResponse);
                }
            } else {
                status.setText("Text to speech could not start. You can still read and type in the other Zoe panels.");
            }
        });
    }

    private void loadVoices() {
        voices.clear();
        for (android.speech.tts.Voice voice : textToSpeech.getVoices()) {
            if ("en".equals(voice.getLocale().getLanguage())) {
                voices.add(voice);
            }
        }
        voices.sort(java.util.Comparator.comparing(voice -> voice.getLocale().toString() + " · " + voice.getName()));
        java.util.List<String> labels = new ArrayList<>();
        for (android.speech.tts.Voice voice : voices) {
            labels.add(voice.getLocale() + " · " + voice.getName());
        }
        if (labels.isEmpty()) {
            labels.add("Default English voice");
        }
        voicePicker.setAdapter(new android.widget.ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, labels));
        String saved = getPreferences(MODE_PRIVATE).getString("voice_name", textToSpeech.getDefaultVoice().getName());
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
                if (position < voices.size()) {
                    textToSpeech.setVoice(voices.get(position));
                    getPreferences(MODE_PRIVATE).edit().putString("voice_name", voices.get(position).getName()).apply();
                }
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
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
        textToSpeech.speak(response, TextToSpeech.QUEUE_FLUSH, null, "zoe-turn");
    }

    private void startListening() {
        if (!active) {
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
                    status.setText("Listening ended with code " + error + ". Start again whenever you are ready.");
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
                    return;
                }
                String heard = alternatives.get(0);
                if (captionMode) {
                    addExchange("CAPTION", heard);
                    startListening();
                    return;
                }
                addExchange("YOU", heard);
                String response = ConversationResponse.forInput(heard);
                addExchange("ZOE", response);
                if (ConversationResponse.isStop(heard)) {
                    active = false;
                    status.setText("Conversation stopped. The microphone is off.");
                    textToSpeech.speak(response, TextToSpeech.QUEUE_FLUSH, null, "zoe-goodbye");
                } else {
                    speakThenListen(response);
                }
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
        status.setText("Conversation stopped. The microphone is off.");
    }

    private void shareTranscript() {
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_SUBJECT, "Zoe conversation")
                .putExtra(Intent.EXTRA_TEXT, transcript.getText().toString());
        startActivity(Intent.createChooser(share, "Share transcript"));
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
        super.onDestroy();
    }
}
