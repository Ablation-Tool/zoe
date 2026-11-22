# Zoe release rules (R8/ProGuard)
# SafeConvert JavaScript bridge: methods are looked up by name from the bundled offline HTML.
-keepclassmembers class research.zoetic.zoe.SafeConvertActivity$SafeBridge {
    @android.webkit.JavascriptInterface <methods>;
}
-keepattributes JavascriptInterface
# Accessibility service entry point declared in the manifest.
-keep class research.zoetic.zoe.ZoeAccessibilityService { *; }
# CameraX / ML Kit ship their own consumer rules; keep annotations for stack traces.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
