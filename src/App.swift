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
    private var worker: Process?
    private var input: FileHandle?
    private var activity: NSObjectProtocol?
    private var pending: URL?
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
        let process = Process()
        process.executableURL = python
        process.arguments = ["-u", root.appendingPathComponent("src/worker.py").path]
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
                            DispatchQueue.main.async { self?.receive(event) }
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
        guard let data = try? JSONSerialization.data(withJSONObject: command), let input = input else { return }
        do { try input.write(contentsOf: data + Data([10])) }
        catch { busy = false; self.error = "The engine connection closed. Restart the app."; endActivity() }
    }

    func receive(_ event: [String: Any]) {
        switch event["type"] as? String {
        case "backend": backend = event["device"] as? String ?? "CPU"
        case "ready":
            authenticated = event["authenticated"] as? Bool ?? authenticated
            setup = !(event["cached"] as? Bool ?? false)
            busy = false; progress = nil; message = ""; endActivity()
            if setup && (event["authenticated"] as? Bool ?? false) { prepare() }
            else if !setup, let source = pending { pending = nil; convert(source) }
        case "status": message = event["message"] as? String ?? "Working…"; progress = nil
        case "authenticated": authenticated = true
        case "download":
            let total = event["total"] as? Double ?? 1
            let completed = event["completed"] as? Double ?? 0
            progress = min(1, completed / max(1, total))
            message = String(format: "Downloading Large… %.2f / %.2f GB", completed / 1_000_000_000, total / 1_000_000_000)
        case "warning": warning = event["message"] as? String ?? ""
        case "progress":
            message = "Transcribing…"
            let total = event["total"] as? Double ?? 1
            progress = min(1, (event["completed"] as? Double ?? 0) / max(1, total))
        case "complete":
            if let path = event["path"] as? String { result = URL(fileURLWithPath: path) }
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
        busy = true; error = ""; message = "Checking MuScriptor Large…"; beginActivity()
        send(["action": "prepare"])
    }

    func connect() {
        let value = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return }
        token = ""; busy = true; error = ""; message = "Connecting to Hugging Face…"; beginActivity()
        send(["action": "auth", "token": value])
    }

    func choose() {
        let panel = NSOpenPanel()
        panel.title = "Choose audio"
        panel.prompt = "Transcribe"
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.audio, .movie]
        panel.allowsOtherFileTypes = true
        panel.begin { response in if response == .OK, let url = panel.url { self.convert(url) } }
    }

    func convert(_ url: URL) {
        guard !busy else { return }
        guard url.isFileURL else { error = "Choose an audio file stored on this Mac."; return }
        if setup { pending = url; filename = url.lastPathComponent; return }
        result = nil; filename = url.lastPathComponent; error = ""; warning = ""; busy = true
        message = "Reading audio…"; progress = nil; beginActivity()
        send(["action": "transcribe", "path": url.path])
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
                self.result = destination; self.needsSave = false
            } catch { self.error = "The MIDI couldn’t be saved there. Try another folder or check free disk space." }
        }
    }

    func reveal() { if let result = result { NSWorkspace.shared.activateFileViewerSelecting([result]) } }
    func another() { result = nil; filename = ""; error = ""; warning = ""; message = "" }
    func retry() {
        error = ""
        if worker == nil || !(worker?.isRunning ?? false) { started = false; start() }
        else if setup { prepare() }
        else { another() }
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
    var body: some View {
        VStack(spacing: 22) {
            Text(state.result == nil ? "AUDIO → MIDI" : "Complete")
                .font(.system(size: 25, weight: .semibold, design: .rounded))
            if state.setup && !state.busy {
                VStack(spacing: 14) {
                    Text("One-time model setup").font(.headline)
                    if state.authenticated {
                        Text("Hugging Face is connected. Resume downloading MuScriptor Large.")
                            .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        Button("Retry Download") { state.prepare() }.buttonStyle(.borderedProminent)
                    } else {
                    Text("Accept the Large model terms on Hugging Face, then paste a read token from that account.")
                        .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    HStack {
                        Link("Model terms", destination: URL(string: "https://huggingface.co/MuScriptor/muscriptor-large")!)
                        Text("·").foregroundStyle(.secondary)
                        Link("Get a read token", destination: URL(string: "https://huggingface.co/settings/tokens")!)
                    }
                    SecureField("Hugging Face read token", text: $state.token).textFieldStyle(.roundedBorder).onSubmit { state.connect() }
                    Button("Connect & Download Large") { state.connect() }.buttonStyle(.borderedProminent).disabled(state.token.isEmpty)
                    }
                    Text("Downloads once. Your audio always stays on this Mac.").font(.caption).foregroundStyle(.secondary)
                }
            } else if let result = state.result {
                Image(systemName: "checkmark.circle.fill").font(.system(size: 42)).foregroundStyle(.green)
                Text(result.lastPathComponent).font(.headline).lineLimit(2).textSelection(.enabled)
                HStack {
                    Button("Save MIDI") { state.save() }.buttonStyle(.borderedProminent)
                    Button("Reveal in Finder") { state.reveal() }
                }
                Button("Convert Another") { state.another() }.buttonStyle(.plain).foregroundStyle(.secondary)
            } else if state.busy {
                if !state.filename.isEmpty { Text(state.filename).font(.headline).lineLimit(2) }
                Text(state.message).foregroundStyle(.secondary).multilineTextAlignment(.center)
                if let progress = state.progress {
                    ProgressView(value: progress).tint(.accentColor)
                    Text("\(Int(progress * 100))%").font(.system(.caption, design: .monospaced)).foregroundStyle(.secondary)
                } else { ProgressView().controlSize(.small) }
            } else {
                Button { state.choose() } label: {
                    VStack(spacing: 12) {
                        Image(systemName: "waveform").font(.system(size: 32, weight: .light))
                        Text("Drop an audio file here").font(.headline)
                        Text("or click to choose").font(.subheadline).foregroundStyle(.secondary)
                        Text("MP3 · WAV · FLAC · M4A / AAC").font(.caption).foregroundStyle(.tertiary)
                    }.frame(maxWidth: .infinity).frame(height: 176)
                    .background(hovering ? Color.accentColor.opacity(0.1) : Color.primary.opacity(0.025))
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(hovering ? Color.accentColor : Color.secondary.opacity(0.3), style: StrokeStyle(lineWidth: 1.5, dash: [6, 5])))
                    .contentShape(Rectangle())
                }.buttonStyle(.plain)
                .onDrop(of: [UTType.fileURL], isTargeted: $hovering) { providers in
                    guard let provider = providers.first else { return false }
                    provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                        let url: URL?
                        if let data = item as? Data { url = URL(dataRepresentation: data, relativeTo: nil) }
                        else { url = item as? URL }
                        if let url = url { DispatchQueue.main.async { state.convert(url) } }
                    }
                    return true
                }
            }
            if !state.error.isEmpty {
                VStack(spacing: 8) {
                    Text(state.error).font(.subheadline).foregroundStyle(.red).multilineTextAlignment(.center)
                    if !state.setup { Button("Try Again") { state.retry() } }
                }
            }
            if !state.warning.isEmpty { Text(state.warning).font(.caption).foregroundStyle(.orange).multilineTextAlignment(.center) }
            Spacer(minLength: 0)
            Text("MuScriptor Large • \(state.backend) • Local").font(.caption).foregroundStyle(.secondary)
        }
        .padding(34).frame(width: 470, height: 445)
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
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 470, height: 445), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
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
