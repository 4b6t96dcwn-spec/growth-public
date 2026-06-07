import SwiftUI

struct SettingsView: View {
    @StateObject private var vm = SettingsViewModel()
    @StateObject private var discovery = BonjourDiscovery()

    var body: some View {
        NavigationStack {
            Form {
                Section("Mac Server") {
                    TextField("Host (IP)", text: $vm.host)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.decimalPad)
                    TextField("API Port", text: $vm.apiPort)
                        .keyboardType(.numberPad)
                    Toggle("HTTPS", isOn: $vm.useHTTPS)
                }
                Section("Auto-discover") {
                    Text(discovery.status)
                    Button("Search for growth Mac") {
                        discovery.start()
                    }
                    if discovery.discoveredHost != nil {
                        Button("Use discovered server") {
                            if let h = discovery.discoveredHost { vm.host = h }
                            if let p = discovery.discoveredPort { vm.apiPort = String(p) }
                        }
                    }
                }
                Section {
                    Button(vm.isTesting ? "Testing…" : "Test Connection") {
                        Task { await vm.testConnection() }
                    }
                    .disabled(vm.isTesting)
                    if let result = vm.testResult {
                        Text(result).font(.footnote)
                    }
                }
                Section("Help") {
                    Text("Run on Mac: cd ~/Projects/growth && ./run.sh --https")
                    Text("Default API port: 21323 (UI: 21322)")
                        .font(.footnote)
                }
            }
            .navigationTitle("Settings")
            .onDisappear { vm.save() }
        }
    }
}