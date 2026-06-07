import SwiftUI

struct DashboardView: View {
    @StateObject private var vm = DashboardViewModel()

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading && vm.status == nil {
                    ProgressView("Loading…")
                } else if let err = vm.error {
                    ContentUnavailableView("Not connected", systemImage: "wifi.slash", description: Text(err))
                } else if let s = vm.status {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 16) {
                            Text(s.plantName ?? "Plant")
                                .font(.title2.bold())
                            Text(s.species ?? "")
                                .foregroundStyle(.secondary)
                            HStack {
                                metric("Height", value: s.latestEntry?.heightCm, unit: "cm")
                                metric("Width", value: s.latestEntry?.widthCm, unit: "cm")
                            }
                            if let lean = s.latestEntry?.leanDirection {
                                Label("Lean: \(lean)", systemImage: "location.north")
                            }
                            Text("Media: \(s.mediaCount)")
                            if !s.goals.isEmpty {
                                Text("Goals").font(.headline)
                                ForEach(s.goals, id: \.self) { g in
                                    Text("• \(g)")
                                }
                            }
                            if let notes = s.latestEntry?.notes {
                                Text(notes).font(.footnote)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                    }
                }
            }
            .navigationTitle("Home")
            .toolbar {
                Button("Refresh") { Task { await vm.refresh() } }
            }
            .task { await vm.refresh() }
        }
    }

    private func metric(_ label: String, value: Double?, unit: String) -> some View {
        VStack {
            Text(label).font(.caption)
            Text(value.map { String(format: "%.0f %@", $0, unit) } ?? "—")
                .font(.title3.bold())
        }
        .frame(maxWidth: .infinity)
    }
}