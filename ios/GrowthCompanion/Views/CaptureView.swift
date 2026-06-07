import SwiftUI
import PhotosUI
import AVFoundation
import CoreMotion

struct CaptureView: View {
    @StateObject private var vm = CaptureViewModel()
    @State private var pickerItems: [PhotosPickerItem] = []
    @State private var showCamera = false
    private let motion = CMMotionManager()

    var body: some View {
        NavigationStack {
            Form {
                Section("Session") {
                    Picker("Type", selection: $vm.sessionType) {
                        ForEach(CaptureSessionType.allCases) { t in
                            Text(t.rawValue).tag(t)
                        }
                    }
                    .onChange(of: vm.sessionType) { _, v in vm.onTypeChange(v) }
                    Text(vm.sessionType.instruction).font(.footnote)
                    Text(vm.session.progress)
                }

                if vm.sessionType == .walk360 {
                    Section("Compass") {
                        Text("Bearing: \(Int(vm.headingDegrees))°")
                        Text("Step \(vm.session.currentBearingIndex + 1) of \(vm.sessionType.targetShotCount)")
                    }
                }

                Section("Add media") {
                    PhotosPicker(selection: $pickerItems, maxSelectionCount: 20, matching: .any(of: [.images, .videos])) {
                        Label("Photo Library", systemImage: "photo.on.rectangle")
                    }
                    .onChange(of: pickerItems) { _, items in
                        Task { await importPickerItems(items) }
                    }
                    Button {
                        showCamera = true
                    } label: {
                        Label("Camera", systemImage: "camera")
                    }
                }

                Section("Note") {
                    TextField("Optional note", text: $vm.session.note)
                }

                if !vm.session.assets.isEmpty {
                    Section("Ready to upload (\(vm.session.assets.count))") {
                        ForEach(vm.session.assets) { a in
                            Text(a.url.lastPathComponent)
                        }
                    }
                }

                Section {
                    Button(vm.isUploading ? "Uploading…" : "Upload to Mac") {
                        Task { await vm.upload() }
                    }
                    .disabled(vm.isUploading || vm.session.assets.isEmpty)
                    Button("Flush offline queue") {
                        Task { await vm.flushQueue() }
                    }
                    if let msg = vm.uploadMessage {
                        Text(msg).font(.footnote)
                    }
                }
            }
            .navigationTitle("Capture")
            .sheet(isPresented: $showCamera) {
                CameraPicker { url, isVideo in
                    Task {
                        if let err = await vm.addAsset(url: url, isVideo: isVideo) {
                            vm.uploadMessage = err
                        }
                    }
                }
            }
            .onAppear { startHeading() }
            .onDisappear { motion.stopDeviceMotionUpdates() }
        }
    }

    private func importPickerItems(_ items: [PhotosPickerItem]) async {
        for item in items {
            let isVideo = item.supportedContentTypes.contains(where: { $0.conforms(to: .movie) })
            if isVideo, let movie = try? await item.loadTransferable(type: VideoFile.self) {
                if let err = await vm.addAsset(url: movie.url, isVideo: true) {
                    vm.uploadMessage = err
                }
            } else if let data = try? await item.loadTransferable(type: Data.self) {
                let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".jpg")
                try? data.write(to: url)
                _ = await vm.addAsset(url: url, isVideo: false)
            }
        }
        pickerItems = []
    }

    private func startHeading() {
        guard motion.isDeviceMotionAvailable else { return }
        motion.deviceMotionUpdateInterval = 0.2
        motion.startDeviceMotionUpdates(using: .xMagneticNorthZVertical, to: .main) { data, _ in
            guard let yaw = data?.attitude.yaw else { return }
            vm.headingDegrees = (yaw * 180 / .pi + 360).truncatingRemainder(dividingBy: 360)
        }
    }
}

struct VideoFile: Transferable {
    let url: URL
    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .movie) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            let dest = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".mov")
            try FileManager.default.copyItem(at: received.file, to: dest)
            return Self(url: dest)
        }
    }
}