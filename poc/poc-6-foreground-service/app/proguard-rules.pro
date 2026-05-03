# Kotlin metadata
-keep class kotlin.** { *; }
-keep class kotlinx.** { *; }
-keepclassmembers class * { @kotlin.Metadata *; }

# AndroidX
-keep class androidx.lifecycle.** { *; }

# Our service must not be obfuscated (Manifest references full name)
-keep class io.livet.poc6.LiveTForegroundService { *; }
-keep class io.livet.poc6.MainActivity { *; }
