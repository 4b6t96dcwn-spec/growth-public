import SwiftUI

struct MainTabView: View {
    var body: some View {
        TabView {
            DashboardView()
                .tabItem { Label("Home", systemImage: "leaf") }
            CaptureView()
                .tabItem { Label("Capture", systemImage: "camera") }
            CareView()
                .tabItem { Label("Care", systemImage: "list.clipboard") }
            HistoryView()
                .tabItem { Label("History", systemImage: "photo.on.rectangle") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gear") }
        }
    }
}