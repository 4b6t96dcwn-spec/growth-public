import SwiftUI

struct HistoryView: View {
    @StateObject private var vm = HistoryViewModel()

    let columns = [GridItem(.adaptive(minimum: 100), spacing: 8)]

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading && vm.items.isEmpty {
                    ProgressView()
                } else if let err = vm.error {
                    ContentUnavailableView("History unavailable", systemImage: "photo", description: Text(err))
                } else if vm.items.isEmpty {
                    ContentUnavailableView("No media yet", systemImage: "photo.on.rectangle")
                } else {
                    ScrollView {
                        LazyVGrid(columns: columns, spacing: 8) {
                            ForEach(vm.items) { item in
                                VStack(spacing: 4) {
                                    if let url = vm.thumbURL(for: item) {
                                        AsyncImage(url: url) { phase in
                                            switch phase {
                                            case .success(let img):
                                                img.resizable().scaledToFill()
                                            default:
                                                Color.gray.opacity(0.2)
                                            }
                                        }
                                        .frame(width: 100, height: 100)
                                        .clipped()
                                        .cornerRadius(8)
                                    }
                                    Text(item.filename)
                                        .font(.caption2)
                                        .lineLimit(1)
                                    Text(item.mediaDate)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("History")
            .toolbar {
                Button("Refresh") { Task { await vm.refresh() } }
            }
            .task { await vm.refresh() }
        }
    }
}