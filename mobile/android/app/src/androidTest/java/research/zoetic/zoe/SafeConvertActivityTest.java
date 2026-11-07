package research.zoetic.zoe;

import static org.junit.Assert.assertTrue;

import android.webkit.WebView;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

@RunWith(AndroidJUnit4.class)
public class SafeConvertActivityTest {
    @Rule
    public ActivityScenarioRule<SafeConvertActivity> activity = new ActivityScenarioRule<>(SafeConvertActivity.class);

    @Before
    public void waitForConverter() throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        while (System.nanoTime() < deadline) {
            String ready = evaluate("document.readyState === 'complete' && !!document.getElementById('help') && document.body.innerText.includes('UNIT CONVERTER')");
            if (ready.contains("true")) {
                return;
            }
            Thread.sleep(50);
        }
        throw new AssertionError("SafeConvert did not finish loading");
    }

    @Test
    public void converterRunsLocallyWithoutReactOrCdn() throws Exception {
        assertTrue("Help state=" + evaluate("document.getElementById('help').className + ':' + getComputedStyle(document.getElementById('help')).display"), evaluate("getComputedStyle(document.getElementById('help')).display").contains("none"));
        String text = evaluate("document.body.innerText");
        assertTrue(text.contains("UNIT CONVERTER"));
        assertTrue(!text.contains("cdnjs"));
        assertTrue(evaluate("document.getElementById('result').textContent").contains("—"));
    }

    @Test
    public void conversionUsesRealUnits() throws Exception {
        evaluate("document.getElementById('to').value='Centimeters';document.getElementById('value').value='1';document.getElementById('value').dispatchEvent(new Event('input'));''");
        String result = evaluate("document.getElementById('result').textContent");
        assertTrue(result.contains("2.54"));
    }

    @Test
    public void exitLeavesOnlyTheConverterCover() throws Exception {
        evaluate("exitHelp();''");
        assertTrue("Help state=" + evaluate("document.getElementById('help').className + ':' + getComputedStyle(document.getElementById('help')).display"), evaluate("getComputedStyle(document.getElementById('help')).display").contains("none"));
        assertTrue(evaluate("getComputedStyle(document.getElementById('converter')).display").contains("block"));
        assertTrue(!evaluate("document.body.innerText").contains("You are not alone"));
    }

    private String evaluate(String script) throws Exception {
        CountDownLatch latch = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>("");
        activity.getScenario().onActivity(activity -> {
            WebView view = activity.findViewById(R.id.safe_web);
            view.evaluateJavascript(script, value -> {
                result.set(value == null ? "" : value);
                latch.countDown();
            });
        });
        assertTrue(latch.await(8, TimeUnit.SECONDS));
        return result.get();
    }
}
