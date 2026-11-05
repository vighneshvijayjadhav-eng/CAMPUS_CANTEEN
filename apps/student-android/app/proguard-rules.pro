# kotlinx.serialization: keep generated serializers for API models.
-keepattributes *Annotation*, InnerClasses
-keepclassmembers class in.ac.aissms.canteen.data.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class in.ac.aissms.canteen.data.**$$serializer { *; }

# Razorpay Checkout (per Razorpay Android integration guide).
-keepclassmembers class * { @android.webkit.JavascriptInterface <methods>; }
-keepattributes JavascriptInterface
-dontwarn com.razorpay.**
-keep class com.razorpay.** { *; }
-optimizations !method/inlining/
-keepclasseswithmembers class * { public void onPayment*(...); }
