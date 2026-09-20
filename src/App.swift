import AppKit
import SwiftUI
import UniformTypeIdentifiers

final class AppState: ObservableObject {
    @Published var busy = true
    @Published var setup = false
    @Published var authenticated = false
    @Published var message = "Checking local environment…"
    @Published var warning = ""
    @Published var error = ""
    @Published var filename = ""
    @Published var progress: Double? = nil
    @Published var backend = "Checking backend"
    @Published var result: URL? = nil
    @Published var token = ""
    @Published var needsSave = false
    @Published var selectedModel = ["small", "medium", "large"].contains(UserDefaults.standard.string(forKey: "selectedModel") ?? "") ? UserDefaults.standard.string(forKey: "selectedModel")! : "large"
    @Published var cachedModels: [String: Bool] = [:]
    @Published var modelDirectory = ""
    @Published var source: URL? = nil
    @Published var destination: URL? = nil
    var modelName: String { selectedModel.capitalized }
    private var worker: Process?
    private var input: FileHandle?
    private var activity: NSObjectProtocol?
    private var started = false
    private var repairing = false
    private var setupProcess: Process?
    let root = URL(fileURLWithPath: Bundle.main.object(forInfoDictionaryKey: "MuScriptorRoot") as? String ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/MuScriptor Local/Engine").path)
    let logs = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/MuScriptor Local")

    func start() {
        guard !started else { return }
        started = true
        busy = true
        error = ""
        message = "Checking local environment…"
        let python = root.appendingPathComponent(".venv/bin/python")
        guard FileManager.default.isExecutableFile(atPath: python.path) else {
            started = false; busy = false
            repair()
            return
        }
        // A portable app update must also refresh an already-installed bridge.
        if Bundle.main.object(forInfoDictionaryKey: "MuScriptorRoot") == nil {
            do {
                let bundledWorker = Bundle.main.resourceURL!.appendingPathComponent("engine/worker.py")
                try Data(contentsOf: bundledWorker).write(to: root.appendingPathComponent("src/worker.py"), options: .atomic)
            } catch {
                started = false; busy = false
                self.error = "The local engine couldn’t be updated. Use Repair Dependencies in the app menu."
                return
            }
        }
        let process = Process()
        process.executableURL = python
        process.arguments = ["-u", root.appendingPathComponent("src/worker.py").path, "--model", selectedModel]
        process.currentDirectoryURL = root
        var env = ProcessInfo.processInfo.environment
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        env["HF_HUB_DISABLE_TELEMETRY"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        process.environment = env
        let output = Pipe(), incoming = Pipe()
        process.standardOutput = output
        process.standardInput = incoming
        do {
            try FileManager.default.createDirectory(at: logs, withIntermediateDirectories: true)
            let logURL = logs.appendingPathComponent("upstream.log")
            if let size = (try? FileManager.default.attributesOfItem(atPath: logURL.path)[.size]) as? NSNumber, size.intValue > 4_000_000 {
                let old = logs.appendingPathComponent("upstream.previous.log")
                try? FileManager.default.removeItem(at: old)
                try? FileManager.default.moveItem(at: logURL, to: old)
            }
            if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
            let log = try FileHandle(forWritingTo: logURL)
            try log.seekToEnd()
            process.standardError = log
            process.terminationHandler = { [weak self, weak process] stopped in
                DispatchQueue.main.async {
                    guard let self = self, self.worker === process else { return }
                    self.endActivity()
                    self.busy = false
                    self.started = false
                    self.worker = nil
                    if !self.repairing { self.error = "The transcription engine stopped. Click Try Again to restart it. Details are in the app’s logs." }
                }
            }
            worker = process
            input = incoming.fileHandleForWriting
            try process.run()
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                var buffer = Data()
                while true {
                    let data = output.fileHandleForReading.availableData
                    if data.isEmpty { break }
                    buffer.append(data)
                    while let newline = buffer.firstIndex(of: 10) {
                        let line = buffer.prefix(upTo: newline)
                        buffer.removeSubrange(...newline)
                        if let event = try? JSONSerialization.jsonObject(with: line) as? [String: Any] {
                            DispatchQueue.main.async {
                                guard let self = self, self.worker === process else { return }
                                self.receive(event)
                            }
                        }
                    }
                }
            }
        } catch {
            worker = nil; started = false; busy = false
            self.error = "The local engine could not start. Use Repair Dependencies in the app menu."
        }
    }

    func send(_ command: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: command), let input = input, worker?.isRunning == true else {
            busy = false; error = "The engine connection closed. Click Try Again to restart it."; endActivity(); return
        }
        do { try input.write(contentsOf: data + Data([10])) }
        catch { busy = false; self.error = "The engine connection closed. Restart the app."; endActivity() }
    }

    func receive(_ event: [String: Any]) {
        switch event["type"] as? String {
        case "backend": backend = event["device"] as? String ?? "CPU"
        case "ready":
            authenticated = event["authenticated"] as? Bool ?? authenticated
            setup = !(event["cached"] as? Bool ?? false)
            cachedModels = event["models"] as? [String: Bool] ?? cachedModels
            modelDirectory = event["directory"] as? String ?? modelDirectory
            busy = false; progress = nil; message = ""; endActivity()
        case "planned":
            if let path = event["path"] as? String { destination = URL(fileURLWithPath: path) }
            busy = false; progress = nil; message = ""; endActivity()
        case "status": message = event["message"] as? String ?? "Working…"; progress = nil
        case "authenticated": authenticated = true
        case "download":
            let total = event["total"] as? Double ?? 1
            let completed = event["completed"] as? Double ?? 0
            progress = min(1, completed / max(1, total))
            modelDirectory = event["directory"] as? String ?? modelDirectory
            message = String(format: "Downloading %@… %.2f / %.2f GB", modelName, completed / 1_000_000_000, total / 1_000_000_000)
        case "warning": warning = event["message"] as? String ?? ""
        case "progress":
            message = "Transcribing…"
            let total = event["total"] as? Double ?? 1
            progress = min(1, (event["completed"] as? Double ?? 0) / max(1, total))
        case "complete":
            if let path = event["path"] as? String { result = URL(fileURLWithPath: path); destination = result }
            needsSave = event["needs_save"] as? Bool ?? false
            busy = false; setup = false; progress = nil; message = ""; endActivity()
            if needsSave { save() }
        case "error":
            busy = false; progress = nil; endActivity()
            error = event["message"] as? String ?? "MuScriptor couldn’t complete this operation."
            if event["code"] as? String == "auth" { setup = true; authenticated = false }
        default: break
        }
    }

    func beginActivity() { if activity == nil { activity = ProcessInfo.processInfo.beginActivity(options: .userInitiated, reason: "Transcribing local audio to MIDI") } }
    func endActivity() { if let activity = activity { ProcessInfo.processInfo.endActivity(activity) }; activity = nil }

    func prepare() {
        guard !busy else { return }
        busy = true; error = ""; warning = ""; message = "Checking MuScriptor \(modelName)…"; beginActivity()
        send(["action": "prepare"])
    }

    func selectModel(_ model: String) {
        guard !busy, model != selectedModel else { return }
        selectedModel = model
        UserDefaults.standard.set(model, forKey: "selectedModel")
        error = ""; warning = ""; progress = nil; modelDirectory = ""
        if worker?.isRunning != true { started = false; start(); return }
        busy = true; message = "Switching to \(modelName)…"
        send(["action": "select_model", "model": model])
    }

    func connect() {
        guard !busy else { return }
        let value = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return }
        token = ""; busy = true; error = ""; message = "Connecting to Hugging Face…"; beginActivity()
        send(["action": "auth", "token": value])
    }

    func choose() {
        let panel = NSOpenPanel()
        panel.title = "Choose audio"
        panel.prompt = "Choose Audio"
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.audio, .movie]
        panel.allowsOtherFileTypes = true
        guard let window = NSApp.keyWindow else { return }
        panel.beginSheetModal(for: window) { response in if response == .OK, let url = panel.url { self.convert(url) } }
    }

    func convert(_ url: URL) {
        guard !busy else { return }
        guard url.isFileURL else { error = "Choose an audio file stored on this Mac."; return }
        source = url; destination = nil; result = nil; filename = url.lastPathComponent
        planOutput()
    }

    func planOutput(directory: URL? = nil) {
        guard let source = source else { return }
        error = ""; warning = ""; busy = true; message = "Checking MIDI destination…"
        var command: [String: Any] = ["action": "plan", "path": source.path]
        if let directory = directory { command["directory"] = directory.path }
        send(command)
    }

    func chooseDestination() {
        let panel = NSOpenPanel()
        panel.title = "Choose MIDI Output Folder"
        panel.prompt = "Use This Folder"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        panel.directoryURL = destination?.deletingLastPathComponent() ?? source?.deletingLastPathComponent()
        guard let window = NSApp.keyWindow else { return }
        panel.beginSheetModal(for: window) { response in
            if response == .OK, let folder = panel.url { self.planOutput(directory: folder) }
        }
    }

    func transcribe() {
        guard !busy, !setup, let source = source, let destination = destination else { return }
        result = nil; error = ""; warning = ""; busy = true
        message = "Reading audio…"; progress = nil; beginActivity()
        send(["action": "transcribe", "path": source.path, "destination": destination.path])
    }

    func save() {
        guard let source = result else { return }
        let panel = NSSavePanel()
        panel.title = "Save MIDI"
        panel.nameFieldStringValue = source.lastPathComponent
        panel.allowedContentTypes = [UTType(filenameExtension: "mid") ?? .data]
        panel.canCreateDirectories = true
        panel.directoryURL = needsSave ? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Music") : source.deletingLastPathComponent()
        panel.begin { response in
            guard response == .OK, let destination = panel.url else { return }
            do {
                if destination.standardizedFileURL != source.standardizedFileURL {
                    try Data(contentsOf: source).write(to: destination, options: .atomic)
                }
                self.result = destination; self.destination = destination; self.needsSave = false; self.error = ""
            } catch { self.error = "The MIDI couldn’t be saved there. Try another folder or check free disk space." }
        }
    }

    func reveal() { if let result = result { NSWorkspace.shared.activateFileViewerSelecting([result]) } }
    func another() { result = nil; source = nil; destination = nil; filename = ""; error = ""; warning = ""; message = ""; needsSave = false }
    func retry() {
        error = ""
        if worker == nil || !(worker?.isRunning ?? false) { started = false; start() }
        else if setup { prepare() }
        else if source != nil && destination == nil { planOutput() }
        else if source != nil && result == nil { transcribe() }
    }
    func stop() {
        input?.closeFile(); input = nil
        setupProcess?.terminate(); setupProcess = nil
        worker?.terminate(); worker = nil; started = false; endActivity()
    }

    func repair() {
        guard !busy else { return }
        repairing = true; stop(); busy = true; error = ""; message = "Repairing local dependencies…"
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        let existingRepair = root.appendingPathComponent("tools/repair.sh")
        if FileManager.default.fileExists(atPath: existingRepair.path) {
            p.arguments = [existingRepair.path]
            p.currentDirectoryURL = root
        } else {
            guard let bootstrap = Bundle.main.url(forResource: "bootstrap", withExtension: "sh") else {
                busy = false; repairing = false; error = "The app’s installer is missing. Download the app again."; return
            }
            p.arguments = [bootstrap.path, root.path]
            message = "Setting up local Python and MuScriptor… First launch needs Internet access."
        }
        try? FileManager.default.createDirectory(at: logs, withIntermediateDirectories: true)
        let logURL = logs.appendingPathComponent("repair.log")
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        p.standardOutput = try? FileHandle(forWritingTo: logURL)
        p.standardError = p.standardOutput
        p.terminationHandler = { finished in DispatchQueue.main.async {
            self.repairing = false
            self.setupProcess = nil
            if finished.terminationStatus == 0 { self.start() }
            else { self.busy = false; self.error = "Dependencies couldn’t be repaired. Check your Internet connection and the repair log." }
        } }
        setupProcess = p
        do { try p.run() } catch { setupProcess = nil; repairing = false; busy = false; self.error = "Repair could not start." }
    }
}

struct ContentView: View {
    @ObservedObject var state: AppState
    @State private var hovering = false

    func pathLabel(_ path: String) -> some View {
        Text(path).font(.system(size: 11, design: .monospaced))
            .foregroundStyle(.secondary).textSelection(.enabled)
            .fixedSize(horizontal: false, vertical: true).frame(maxWidth: .infinity, alignment: .leading)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("AUDIO → MIDI").font(.system(size: 25, weight: .semibold, design: .rounded))
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Model").font(.headline)
                        Spacer()
                        Text(state.cachedModels[state.selectedModel] == true ? "Downloaded" : "Download required")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Picker("Model", selection: Binding(get: { state.selectedModel }, set: { state.selectModel($0) })) {
                        Text("Small").tag("small")
                        Text("Medium").tag("medium")
                        Text("Large").tag("large")
                    }.pickerStyle(.segmented).labelsHidden().disabled(state.busy)
                    Text("Small uses less memory · Medium balances size and accuracy · Large favors accuracy")
                        .font(.caption).foregroundStyle(.secondary)
                }

                if state.busy {
                    VStack(spacing: 12) {
                        if !state.filename.isEmpty { Text(state.filename).font(.headline).lineLimit(2) }
                        Text(state.message).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        if let progress = state.progress {
                            ProgressView(value: progress).tint(.accentColor)
                            Text("\(Int(progress * 100))%").font(.system(.caption, design: .monospaced)).foregroundStyle(.secondary)
                        } else { ProgressView().controlSize(.small) }
                    }.frame(maxWidth: .infinity).padding(.vertical, 18)
                } else if let result = state.result {
                    VStack(spacing: 12) {
                        Image(systemName: "checkmark.circle.fill").font(.system(size: 36)).foregroundStyle(.green)
                        Text("Transcription complete").font(.headline)
                        Text(result.lastPathComponent).lineLimit(2).textSelection(.enabled)
                        HStack {
                            Button("Save MIDI Copy…") { state.save() }.buttonStyle(.borderedProminent)
                            Button("Reveal in Finder") { state.reveal() }
                        }
                        Button("Convert Another") { state.another() }.buttonStyle(.plain).foregroundStyle(.secondary)
                    }.frame(maxWidth: .infinity)
                } else {
                    if state.setup {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Set up MuScriptor \(state.modelName)").font(.headline)
                            Text("Accept this model’s terms on Hugging Face. Each size needs its own acceptance; downloads are kept for future use.")
                                .font(.subheadline).foregroundStyle(.secondary)
                            HStack {
                                Link("\(state.modelName) model terms", destination: URL(string: "https://huggingface.co/MuScriptor/muscriptor-\(state.selectedModel)")!)
                                Text("·").foregroundStyle(.secondary)
                                Link("Get a read token", destination: URL(string: "https://huggingface.co/settings/tokens")!)
                            }
                            if state.authenticated {
                                Button("Download \(state.modelName)") { state.prepare() }.buttonStyle(.borderedProminent)
                            } else {
                                SecureField("Hugging Face read token", text: $state.token).textFieldStyle(.roundedBorder).onSubmit { state.connect() }
                                Button("Connect & Download \(state.modelName)") { state.connect() }
                                    .buttonStyle(.borderedProminent)
                                    .disabled(state.token.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                            }
                        }.padding(16).background(Color.primary.opacity(0.035)).clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    if state.source != nil {
                        HStack {
                            Image(systemName: "waveform").font(.title2)
                            Text(state.filename).font(.headline).lineLimit(2)
                            Spacer()
                            Button("Change Audio…") { state.choose() }
                        }
                    } else {
                        Button { state.choose() } label: {
                            VStack(spacing: 10) {
                                Image(systemName: "waveform").font(.system(size: 30, weight: .light))
                                Text("Drop an audio file here").font(.headline)
                                Text("or click to choose").font(.subheadline).foregroundStyle(.secondary)
                                Text("MP3 · WAV · FLAC · M4A / AAC").font(.caption).foregroundStyle(.tertiary)
                            }.frame(maxWidth: .infinity).frame(height: 155)
                            .background(hovering ? Color.accentColor.opacity(0.1) : Color.primary.opacity(0.025))
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(hovering ? Color.accentColor : Color.secondary.opacity(0.3), style: StrokeStyle(lineWidth: 1.5, dash: [6, 5])))
                            .contentShape(Rectangle())
                        }.buttonStyle(.plain)
                    }
                }

                if let destination = state.destination {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(state.result == nil ? "MIDI destination" : "MIDI saved to").font(.headline)
                            Spacer()
                            if !state.busy && state.result == nil {
                                Button("Change Folder…") { state.chooseDestination() }
                            }
                        }
                        pathLabel(destination.path)
                        if state.result == nil {
                            Text("Existing files are kept. A number is added if this name is taken.")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }.padding(14).background(Color.primary.opacity(0.035)).clipShape(RoundedRectangle(cornerRadius: 12))
                    if !state.busy && state.result == nil {
                        Button("Transcribe with \(state.modelName)") { state.transcribe() }
                            .buttonStyle(.borderedProminent).controlSize(.large).disabled(state.setup)
                    }
                }

                if !state.error.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(state.error).font(.subheadline).foregroundStyle(.red)
                        Button("Try Again") { state.retry() }.disabled(state.busy)
                    }
                }
                if !state.warning.isEmpty { Text(state.warning).font(.caption).foregroundStyle(.orange) }
                Divider()
                if !state.modelDirectory.isEmpty {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("Model download folder").font(.caption).fontWeight(.medium)
                        pathLabel(state.modelDirectory)
                    }
                }
                Text("MuScriptor \(state.modelName) • \(state.backend) • Audio stays on this Mac")
                    .font(.caption).foregroundStyle(.secondary)
            }.padding(28)
        }.frame(width: 560, height: 730)
        .onDrop(of: [UTType.fileURL], isTargeted: $hovering) { providers in
            guard !state.busy, let provider = providers.first else { return false }
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                let url: URL?
                if let data = item as? Data { url = URL(dataRepresentation: data, relativeTo: nil) }
                else { url = item as? URL }
                if let url = url { DispatchQueue.main.async { state.convert(url) } }
            }
            return true
        }
        .onAppear { state.start() }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    let state = AppState()
    var window: NSWindow!
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let menu = NSMenu()
        let main = NSMenuItem(); let submenu = NSMenu()
        submenu.addItem(withTitle: "About MuScriptor Local", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        submenu.addItem(.separator())
        let repair = submenu.addItem(withTitle: "Repair Dependencies…", action: #selector(repairDependencies), keyEquivalent: "")
        repair.target = self
        let logs = submenu.addItem(withTitle: "Show Logs", action: #selector(showLogs), keyEquivalent: "")
        logs.target = self
        submenu.addItem(.separator())
        submenu.addItem(withTitle: "Quit MuScriptor Local", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        main.submenu = submenu; menu.addItem(main)
        let editItem = NSMenuItem(); let edit = NSMenu(title: "Edit")
        edit.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit; menu.addItem(editItem); NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: 730), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "MuScriptor Local"
        window.contentView = NSHostingView(rootView: ContentView(state: state))
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }
    @objc func repairDependencies() { state.repair() }
    @objc func showLogs() { NSWorkspace.shared.open(state.logs) }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ notification: Notification) { state.stop() }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil); return true
    }
}

let application = NSApplication.shared
let delegate = AppDelegate()
application.delegate = delegate
application.run()
