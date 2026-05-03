// settings.gradle.kts — top-level Gradle settings for PoC-6
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
        // Aliyun mirror for fastest CN downloads
        maven { url = uri("https://maven.aliyun.com/repository/google") }
        maven { url = uri("https://maven.aliyun.com/repository/public") }
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://maven.aliyun.com/repository/google") }
        maven { url = uri("https://maven.aliyun.com/repository/public") }
    }
}

rootProject.name = "livet-poc6"
include(":app")
