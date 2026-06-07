import SwiftUI

struct CareView: View {
    @StateObject private var vm = CareViewModel()

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading && vm.markdown.isEmpty {
                    ProgressView()
                } else if let err = vm.error {
                    ContentUnavailableView("Care unavailable", systemImage: "leaf", description: Text(err))
                } else {
                    ScrollView {
                        Text(vm.markdown)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                    }
                }
            }
            .navigationTitle("Care")
            .toolbar {
                if !vm.date.isEmpty {
                    Text(vm.date).font(.caption)
                }
                Button("Refresh") { Task { await vm.refresh() } }
            }
            .task { await vm.refresh() }
        }
    }
}