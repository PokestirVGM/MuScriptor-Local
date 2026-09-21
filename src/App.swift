import AppKit
import SwiftUI
import UniformTypeIdentifiers
import Darwin

struct ProcessorChoice: Identifiable { let id: String; let label: String }

final class AppState: ObservableObject {
    @Published var showingAppInfo = false
    @Published var busy = true
    @Published var setup = false
    @Published var authenticated = false
    @Published var message = "Checking local environment…"
    @Published var warning = ""
    @Published var error = ""
    @Published var filename = ""
    @Published var progress: Double? = nil
    @Published var canFinish = false
    @Published var finishing = false
    @Published var completedSeconds = 0.0
    private var transcriptionID: String?
    @Published var backend = "Checking backend"
    @Published var processorDetail = ""
    @Published var processors: [ProcessorChoice] = []
    @Published var selectedProcessor = UserDefaults.standard.string(forKey: "selectedProcessor") ?? "auto"
    @Published var result: URL? = nil
    @Published var token = ""
    @Published var needsSave = false
    @Published var selectedModel = ["small", "medium", "large"].contains(UserDefaults.standard.string(forKey: "selectedModel") ?? "") ? UserDefaults.standard.string(forKey: "selectedModel")! : "large"
    @Published var cachedModels: [String: Bool] = [:]
    @Published var modelDirectory = ""
    @Published var source: URL? = nil
    @Published var destination: URL? = nil
    @Published var instrumentGroups: [String] = []
    @Published var selectedInstruments: [String] = []
    @Published var quantizeMIDI = false
    @Published var tempoMode = "auto"
    @Published var tempoBPM = "120"
    @Published var tempoMeter = "auto"
    @Published var tempoUnit = "auto"
    @Published var tempoDownbeat = "0"
    @Published var tempoSubdivision = "auto"
    @Published var tempoFactor = "1"
    @Published var tempoAnchors = ""
    @Published var tempoChanges = ""
    @Published var timingSummary = ""
    @Published var hasSession = false
    @Published var recoveryPath: String? = nil
    @Published var exportReadiness = "Check export requirements from the app menu."
    @Published var fluidsynthReady = false
    private var restoreAfterRestart: String? = nil
    private var restoreLatestAfterRestart = false
    private var pendingTiming: [String: Any]? = nil
    @Published var savedTiming = ""
    var timingKey: String { String(data: (try? JSONSerialization.data(withJSONObject: timingOptions, options: .sortedKeys)) ?? Data(), encoding: .utf8) ?? "" }
    var hasUnsavedTiming: Bool { hasSession && savedTiming != timingKey }
    var canCancel: Bool { busy && setupProcess == nil && worker != nil }
    func confirmDiscardTiming() -> Bool {
        guard hasUnsavedTiming else { return true }
        let alert = NSAlert(); alert.messageText = "Discard unsaved timing changes?"
        alert.informativeText = "Use Save Session or Apply & save new MIDI to keep these changes. The last applied session remains recoverable."
        alert.addButton(withTitle: "Keep Editing"); alert.addButton(withTitle: "Discard Changes")
        return alert.runModal() == .alertSecondButtonReturn
    }

    func checkExports() {
        guard !busy, webURL == nil else { return }
        busy = true; send(["action": "capabilities"])
    }
    func finishTranscription() {
        guard busy, canFinish, !finishing, let id = transcriptionID else { return }
        finishing = true; canFinish = false
        message = "Finishing completed sections and saving MIDI…"
        send(["action": "finish_transcription", "run_id": id])
    }

    func cancelOperation() {
        guard busy, setupProcess == nil, let process = worker else { return }
        canFinish = false; finishing = false; transcriptionID = nil
        restoreAfterRestart = hasSession ? recoveryPath : nil
        pendingTiming = hasSession ? timingOptions : nil
        worker = nil; input?.closeFile(); input = nil
        if process.isRunning {
            if killpg(process.processIdentifier, SIGKILL) != 0 { kill(process.processIdentifier, SIGKILL) }
            process.waitUntilExit()
        }
        hasSession = false
        started = false; endActivity(); busy = false; progress = nil; warning = "Operation cancelled. Your file and settings were kept."
        start()
    }
    func openSession(path: String? = nil) {
        guard !busy, webURL == nil else { return }
        if let path = path {
            if pendingTiming == nil && !confirmDiscardTiming() { return }
            busy = true; error = ""; send(["action": "load_session", "path": path]); return
        }
        let panel = NSOpenPanel(); panel.title = "Open MuScriptor Session"
        panel.allowedContentTypes = [UTType(filenameExtension: "muscriptor") ?? .data]
        panel.allowsMultipleSelection = false
        panel.begin { response in if response == .OK, let url = panel.url { self.openSession(path: url.path) } }
    }
    func saveSession() {
        guard !busy, hasSession else { return }
        let panel = NSSavePanel(); panel.title = "Save Session"
        panel.nameFieldStringValue = (filename as NSString).deletingPathExtension + ".muscriptor"
        panel.allowedContentTypes = [UTType(filenameExtension: "muscriptor") ?? .data]
        panel.begin { response in
            if response == .OK, let url = panel.url {
                self.busy = true; self.send(["action": "save_session", "path": url.path, "timing": self.timingOptions])
            }
        }
    }
    func applySession() {
        guard !busy, hasSession else { return }
        busy = true; warning = ""; error = ""; message = "Updating MIDI…"
        var command: [String: Any] = ["action": "reexport_session", "timing": timingOptions]
        if let destination = destination { command["destination"] = destination.path }
        send(command)
    }
    func restoreTiming(_ t: [String: Any]) {
        tempoMode = t["mode"] as? String ?? "auto"; tempoMeter = t["meter"] as? String ?? "auto"
        tempoUnit = t["unit"] as? String ?? "auto"; quantizeMIDI = t["quantize"] as? Bool ?? false
        tempoBPM = t["bpm"].map { String(describing: $0) } ?? "120"
        tempoDownbeat = t["first_downbeat"].map { String(describing: $0) } ?? "0"
        tempoSubdivision = t["subdivision"].map { String(describing: $0) } ?? "auto"
        tempoFactor = String(format: "%g", Double(t["factor"].map { String(describing: $0) } ?? "1") ?? 1)
        tempoAnchors = t["anchors"] as? String ?? (t["anchors"] as? [[Double]])?.map { "\($0[0]), \($0[1])" }.joined(separator: "\n") ?? ""; tempoChanges = t["meter_changes"] as? String ?? ""
    }
    var timingOptions: [String: Any] {
        ["mode": tempoMode, "bpm": tempoBPM, "meter": tempoMeter, "unit": tempoUnit,
         "first_downbeat": tempoDownbeat,
         "quantize": quantizeMIDI, "subdivision": tempoSubdivision, "factor": tempoFactor,
         "anchors": tempoAnchors, "meter_changes": tempoChanges]
    }
    func previewRhythm() {
        busy = true; error = ""; message = "Preparing click preview…"
        send(["action": "preview_rhythm", "timing": timingOptions])
    }
    @Published var createAB = false
    @Published var soundfont: URL? = nil
    @Published var abResult: URL? = nil
    @Published var webURL: URL? = nil
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
                guard let resources = Bundle.main.resourceURL else { throw CocoaError(.fileNoSuchFile) }
                let installer = Process()
                installer.executableURL = python
                installer.arguments = [resources.appendingPathComponent("engine_install.py").path, root.path,
                    resources.appendingPathComponent("engine/worker.py").path,
                    resources.appendingPathComponent("engine/upstream/muscriptor").path]
                try installer.run(); installer.waitUntilExit()
                if installer.terminationStatus != 0 { throw CocoaError(.fileWriteUnknown) }
            } catch {
                started = false; busy = false
                self.error = "The local engine couldn’t be updated. Use Repair Dependencies in the app menu."
                return
            }
        }
        let process = Process()
        process.executableURL = python
        process.arguments = ["-u", root.appendingPathComponent("src/worker.py").path, "--model", selectedModel, "--device", selectedProcessor]
        process.currentDirectoryURL = root
        var env = ProcessInfo.processInfo.environment
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        env["HF_HUB_DISABLE_TELEMETRY"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        // Finder launches do not inherit a shell's Homebrew PATH.
        env["PATH"] = (env["PATH"] ?? "/usr/bin:/bin") + ":/opt/homebrew/bin:/usr/local/bin"
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
                    if self.webURL != nil {
                        self.restoreLatestAfterRestart = true
                        self.restoreAfterRestart = nil; self.pendingTiming = nil
                    } else {
                        self.restoreAfterRestart = self.hasSession ? self.recoveryPath : nil
                        self.pendingTiming = self.restoreAfterRestart != nil ? self.timingOptions : nil
                    }
                    self.hasSession = false
                    self.worker = nil
                    self.webURL = nil
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
        case "web_ready":
            guard let address = event["url"] as? String, let url = URL(string: address), url.scheme == "http", url.host == "127.0.0.1", url.port != nil else { return }
            webURL = url; busy = false; progress = nil; message = ""; endActivity()
            NSWorkspace.shared.open(url)
        case "backend":
            backend = event["device"] as? String ?? "CPU"
            processorDetail = event["detail"] as? String ?? ""
            processors = (event["devices"] as? [[String: Any]] ?? []).compactMap { device in
                guard let id = device["id"] as? String, let name = device["name"] as? String else { return nil }
                let backend = device["backend"] as? String ?? ""
                return ProcessorChoice(id: id, label: "\(backend) — \(name)")
            }
            selectedProcessor = event["requested_device"] as? String ?? "auto"
            UserDefaults.standard.set(selectedProcessor, forKey: "selectedProcessor")
        case "capabilities":
            fluidsynthReady = event["fluidsynth"] as? Bool ?? false
            let sheets = event["sheets"] as? Bool ?? false
            exportReadiness = "MIDI: ready. Sheet music in Web GUI: " + (sheets ? "ready." : "install MuseScore 4+.") + " A/B audio: " + (fluidsynthReady ? "choose a local SF2 SoundFont." : "install FluidSynth and choose a local SF2 SoundFont.")
            busy = false; message = ""
        case "session_saved":
            savedTiming = timingKey; busy = false; message = "Session saved."
        case "session_loaded":
            hasSession = true; source = nil; destination = nil; abResult = nil
            filename = event["name"] as? String ?? "Recording"
            if let timing = event["timing"] as? [String: Any] { restoreTiming(timing) }
        case "ready":
            recoveryPath = event["recovery_path"] as? String
            instrumentGroups = event["instruments"] as? [String] ?? instrumentGroups
            authenticated = event["authenticated"] as? Bool ?? authenticated
            setup = !(event["cached"] as? Bool ?? false)
            cachedModels = event["models"] as? [String: Bool] ?? cachedModels
            modelDirectory = event["directory"] as? String ?? modelDirectory
            busy = false; progress = nil; message = ""; endActivity()
            if restoreLatestAfterRestart {
                restoreLatestAfterRestart = false; restoreAfterRestart = recoveryPath
            }
            if let path = restoreAfterRestart { restoreAfterRestart = nil; openSession(path: path) }
            else if source != nil && destination == nil { planOutput() }
        case "planned":
            if let path = event["path"] as? String { destination = URL(fileURLWithPath: path) }
            busy = false; progress = nil; message = ""; endActivity()
        case "status": canFinish = false; message = event["message"] as? String ?? "Working…"; progress = nil
        case "authenticated": authenticated = true
        case "download":
            let total = event["total"] as? Double ?? 1
            let completed = event["completed"] as? Double ?? 0
            progress = min(1, completed / max(1, total))
            modelDirectory = event["directory"] as? String ?? modelDirectory
            message = String(format: "Downloading %@… %.2f / %.2f GB", modelName, completed / 1_000_000_000, total / 1_000_000_000)
        case "warning":
            if let notice = event["message"] as? String {
                warning += warning.isEmpty ? notice : "\n\n" + notice
            }
        case "progress":
            canFinish = (event["can_finish"] as? Bool ?? false) && !finishing
            completedSeconds = event["completed_seconds"] as? Double ?? 0
            message = finishing ? "Finishing completed sections and saving MIDI…" : "Transcribing…"
            let total = event["total"] as? Double ?? 1
            progress = min(1, (event["completed"] as? Double ?? 0) / max(1, total))
        case "rhythm_preview":
            busy = false; progress = nil
            timingSummary = event["message"] as? String ?? ""
            if let path = event["path"] as? String { NSWorkspace.shared.open(URL(fileURLWithPath: path)) }
        case "complete":
            canFinish = false; finishing = false; transcriptionID = nil
            hasSession = event["session"] as? Bool ?? false
            if hasSession { recoveryPath = event["recovery_path"] as? String }
            timingSummary = event["timing_summary"] as? String ?? ""
            abResult = (event["ab_path"] as? String).map { URL(fileURLWithPath: $0) }
            if let path = event["path"] as? String { result = URL(fileURLWithPath: path); destination = result }
            needsSave = event["needs_save"] as? Bool ?? false
            busy = false; progress = nil; message = ""; endActivity()
            savedTiming = timingKey
            if let timing = pendingTiming { pendingTiming = nil; restoreTiming(timing) }
            if needsSave { save() }
        case "error":
            pendingTiming = nil
            canFinish = false; finishing = false; transcriptionID = nil
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

    func selectProcessor(_ processor: String) {
        guard !busy, webURL == nil, processor != selectedProcessor else { return }
        busy = true; error = ""; message = "Switching processor…"
        send(["action": "select_device", "device": processor])
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
        guard !busy, confirmDiscardTiming() else { return }
        guard url.isFileURL else { error = "Choose an audio file stored on this Mac."; return }
        hasSession = false; timingSummary = ""; source = url; destination = nil; result = nil; abResult = nil; filename = url.lastPathComponent
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
        result = nil; abResult = nil; error = ""; warning = ""; busy = true
        message = "Reading audio…"; progress = nil; beginActivity()
        transcriptionID = UUID().uuidString; finishing = false; canFinish = false; completedSeconds = 0
        var command: [String: Any] = ["action": "transcribe", "run_id": transcriptionID!, "path": source.path,
            "destination": destination.path, "instruments": selectedInstruments,
            "quantize": quantizeMIDI, "create_ab": createAB, "timing": timingOptions]
        if let soundfont = soundfont { command["soundfont"] = soundfont.path }
        send(command)
    }

    func chooseSoundfont() {
        let panel = NSOpenPanel()
        panel.title = "Choose a local SF2 SoundFont"
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [UTType(filenameExtension: "sf2") ?? .data]
        guard let window = NSApp.keyWindow else { return }
        panel.beginSheetModal(for: window) { response in
            if response == .OK { self.soundfont = panel.url }
        }
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
    func another() { guard confirmDiscardTiming() else { return }; hasSession = false; timingSummary = ""; result = nil; abResult = nil; source = nil; destination = nil; filename = ""; error = ""; warning = ""; message = ""; needsSave = false }
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
        if let process = worker, process.isRunning {
            if webURL != nil {
                // Stop any active web inference before releasing its model.
                // Include optional MuseScore/FluidSynth children of this worker.
                if killpg(process.processIdentifier, SIGKILL) != 0 { kill(process.processIdentifier, SIGKILL) }
                process.waitUntilExit()
            } else {
                if killpg(process.processIdentifier, SIGKILL) != 0 { kill(process.processIdentifier, SIGKILL) }
                process.waitUntilExit()
            }
        }
        worker = nil; webURL = nil; started = false; endActivity()
    }

    func openWebGUI() {
        if let url = webURL { NSWorkspace.shared.open(url); return }
        guard !busy, !setup, confirmDiscardTiming() else { return }
        busy = true; error = ""; message = "Opening the local web GUI…"; beginActivity()
        send(["action": "web_gui"])
    }

    func returnToDesktop() {
        guard webURL != nil else { return }
        restoreLatestAfterRestart = true
        restoreAfterRestart = nil; pendingTiming = nil; hasSession = false
        stop(); start()
    }

    func repair() {
        guard !busy else { return }
        if hasSession {
            restoreAfterRestart = recoveryPath
            pendingTiming = recoveryPath != nil ? timingOptions : nil
            hasSession = false
        }
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
    @Environment(\.colorScheme) private var colorScheme
    @State private var hovering = false
    @State private var instrumentSearch = ""
    @State private var instrumentListHeight: CGFloat = 100
    @State private var instrumentResizeStart: CGFloat?

    private func timingEditor(_ title: String, text: Binding<String>, example: String, help: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            ZStack(alignment: .topLeading) {
                TextEditor(text: text)
                    .font(.system(.body, design: .monospaced))
                    .scrollContentBackground(.hidden)
                    .padding(5)
                    .accessibilityLabel(title)
                if text.wrappedValue.isEmpty {
                    Text(example).font(.system(.body, design: .monospaced))
                        .foregroundStyle(.tertiary).padding(.horizontal, 10).padding(.vertical, 7)
                        .allowsHitTesting(false)
                        .accessibilityHidden(true)
                }
            }.frame(height: 62)
                .background(Color(nsColor: .textBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.secondary.opacity(0.2)))
            Text(help).font(.caption).foregroundStyle(.secondary)
        }
    }

    func instrumentLabel(_ name: String) -> String {
        name.replacingOccurrences(of: "_", with: " ").capitalized
    }

    var transcriptionOptions: some View {
        VStack(alignment: .leading, spacing: 12) {
            if state.result == nil {
            Text("Instruments").font(.headline)
            Text("Leave empty to detect any supported instrument.")
                .font(.caption).foregroundStyle(.secondary)
            ForEach(state.selectedInstruments, id: \.self) { name in
                HStack {
                    Text(instrumentLabel(name))
                    Spacer()
                    Button { state.selectedInstruments.removeAll { $0 == name } } label: {
                        Image(systemName: "xmark.circle.fill")
                    }.buttonStyle(.plain).accessibilityLabel("Remove \(instrumentLabel(name))")
                }.padding(7).background(Color.accentColor.opacity(0.1)).cornerRadius(7)
            }
            TextField("Search instruments", text: $instrumentSearch).textFieldStyle(.roundedBorder)
            VStack(spacing: 3) {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 6) {
                    let matches = state.instrumentGroups.filter {
                        !state.selectedInstruments.contains($0) &&
                        (instrumentSearch.isEmpty || instrumentLabel($0).localizedCaseInsensitiveContains(instrumentSearch))
                    }
                    if matches.isEmpty { Text("No matching instruments").foregroundStyle(.secondary) }
                    ForEach(matches, id: \.self) { name in
                        Button {
                            state.selectedInstruments.append(name)
                            instrumentSearch = ""
                        } label: {
                            Label(instrumentLabel(name), systemImage: "plus.circle")
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }.buttonStyle(.plain).padding(.vertical, 3)
                    }
                }
            }.frame(height: instrumentListHeight)
                HStack {
                    Spacer()
                    Capsule().fill(Color.secondary.opacity(0.5)).frame(width: 32, height: 3)
                    Spacer()
                }.frame(height: 12).contentShape(Rectangle())
                    .help("Drag to resize the instrument list")
                    .onHover { hovering in
                        if hovering { NSCursor.resizeUpDown.push() } else { NSCursor.pop() }
                    }
                    .gesture(DragGesture(minimumDistance: 0, coordinateSpace: .global)
                        .onChanged { value in
                            if instrumentResizeStart == nil { instrumentResizeStart = instrumentListHeight }
                            instrumentListHeight = min(320, max(80, (instrumentResizeStart ?? 100) + value.translation.height))
                        }
                        .onEnded { _ in instrumentResizeStart = nil })
                    .accessibilityElement()
                    .accessibilityLabel("Resize instrument list")
                    .accessibilityValue("\(Int(instrumentListHeight)) points")
                    .accessibilityAdjustableAction { direction in
                        switch direction {
                        case .increment: instrumentListHeight = min(320, instrumentListHeight + 20)
                        case .decrement: instrumentListHeight = max(80, instrumentListHeight - 20)
                        @unknown default: break
                        }
                    }
            }
            }
            Divider()
            HStack(alignment: .bottom, spacing: 16) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("Tempo").font(.caption).foregroundStyle(.secondary)
                    Picker("Tempo", selection: $state.tempoMode) {
                        Text("Auto").tag("auto"); Text("Manual").tag("manual")
                    }.labelsHidden().frame(minWidth: 110, maxWidth: .infinity, alignment: .leading)
                }
                VStack(alignment: .leading, spacing: 5) {
                    Text("Time signature").font(.caption).foregroundStyle(.secondary)
                    let meters = ["auto", "2/4", "3/4", "4/4", "6/8", "9/8", "12/8", "5/4", "7/8"]
                    Picker("Time signature", selection: Binding(get: { meters.contains(state.tempoMeter) ? state.tempoMeter : "custom" }, set: { state.tempoMeter = $0 == "custom" ? "5/8" : $0 })) {
                        ForEach(meters, id: \.self) { meter in Text(meter == "auto" ? "Auto" : meter).tag(meter) }
                        Text("Custom…").tag("custom")
                    }.labelsHidden().frame(minWidth: 110, maxWidth: .infinity, alignment: .leading)
                }
                Toggle("Strict quantization", isOn: $state.quantizeMIDI)
                    .toggleStyle(.checkbox).fixedSize(horizontal: true, vertical: false)
            }
            if !["auto", "2/4", "3/4", "4/4", "6/8", "9/8", "12/8", "5/4", "7/8"].contains(state.tempoMeter) {
                TextField("Custom time signature", text: $state.tempoMeter).textFieldStyle(.roundedBorder)
            }
            if state.tempoMode == "manual" {
                HStack {
                    Text("BPM"); TextField("BPM", text: $state.tempoBPM).textFieldStyle(.roundedBorder).frame(width: 65)
                    Text("Sets the grid; playback stays at the original speed.").font(.caption).foregroundStyle(.secondary)
                }
            }
            if state.quantizeMIDI {
                Text("Snaps note starts and ends to the grid. Check the click first: an incorrect grid can make rhythm worse. Turn off to restore original timing.").font(.caption).foregroundStyle(.secondary)
                Picker("Snap to", selection: $state.tempoSubdivision) {
                    Text("Auto").tag("auto"); Text("Eighth notes").tag("2")
                    Text("Sixteenth notes").tag("4"); Text("Eighth-note triplets").tag("3")
                }
            }
            DisclosureGroup("Advanced timing") {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Tempo sets the grid without changing playback speed. Quantization moves notes.")
                        .font(.caption).foregroundStyle(.secondary)
                    HStack(alignment: .top, spacing: 16) {
                        VStack(alignment: .leading, spacing: 5) {
                            Text("BPM beat unit").font(.caption).foregroundStyle(.secondary)
                            Picker("BPM beat unit", selection: $state.tempoUnit) {
                                Text("From time signature").tag("auto"); Text("Quarter note").tag("quarter")
                                Text("Dotted quarter").tag("dotted-quarter"); Text("Eighth note").tag("eighth")
                            }.labelsHidden().frame(maxWidth: .infinity, alignment: .leading)
                        }
                        VStack(alignment: .leading, spacing: 5) {
                            Text("Detected pulse").font(.caption).foregroundStyle(.secondary)
                            Picker("Detected pulse", selection: $state.tempoFactor) {
                                Text("Normal").tag("1"); Text("Half tempo").tag("0.5"); Text("Double tempo").tag("2")
                            }.labelsHidden().frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    Text("6/8 usually counts dotted-quarter beats. Check Auto’s meter suggestions; enter corrections below.")
                        .font(.caption).foregroundStyle(.secondary)
                    if state.tempoMode == "manual" {
                        VStack(alignment: .leading, spacing: 5) {
                            Text("First downbeat (seconds)").font(.caption).foregroundStyle(.secondary)
                            TextField("Seconds", text: $state.tempoDownbeat).textFieldStyle(.roundedBorder).frame(width: 100)
                        }
                    }
                    timingEditor("Beat anchors", text: $state.tempoAnchors, example: "0.5, 1\n2.5, 5",
                                 help: "Seconds, beat number. Use at least two anchors; beat 1 is the first downbeat.")
                    timingEditor("Time-signature changes", text: $state.tempoChanges, example: "9, 3/4",
                                 help: "Bar number, signature. Bar 1 starts at the first downbeat.")
                }.padding(.top, 8).frame(maxWidth: .infinity, alignment: .leading)
            }
            if !state.timingSummary.isEmpty { Text(state.timingSummary).font(.caption).textSelection(.enabled) }
            if state.result != nil {
                HStack {
                    Button("Apply & save new MIDI") { state.applySession() }
                    Button("Save Session…") { state.saveSession() }
                    Button("Preview click") { state.previewRhythm() }
                }
            }
            if state.exportReadiness != "Check export requirements from the app menu." {
                Text(state.exportReadiness).font(.caption).foregroundStyle(.secondary)
            }
            Toggle("Create A/B audio render", isOn: $state.createAB).toggleStyle(.checkbox)
            if state.createAB {
                Text("Original audio on the left; performance-timing MIDI synthesis on the right. Requires FluidSynth and a local SF2 SoundFont.")
                    .font(.caption).foregroundStyle(.secondary)
                Button("Choose SoundFont…") { state.chooseSoundfont() }
                if let soundfont = state.soundfont { pathLabel(soundfont.path) }
                else { Text("Choose a SoundFont to enable local audio rendering.").font(.caption).foregroundStyle(.secondary) }
            }
        }.padding(14).background(Color.primary.opacity(0.035)).clipShape(RoundedRectangle(cornerRadius: 12))
            .disabled(state.busy)
    }

    func pathLabel(_ path: String) -> some View {
        Text(path).font(.system(size: 11, design: .monospaced))
            .foregroundStyle(.secondary).textSelection(.enabled)
            .fixedSize(horizontal: false, vertical: true).frame(maxWidth: .infinity, alignment: .leading)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(spacing: 12) {
                        if let logoURL = Bundle.main.url(forResource: "muscriptor-header-\(colorScheme == .dark ? "dark" : "light")", withExtension: "png"),
                           let logo = NSImage(contentsOf: logoURL) {
                            Image(nsImage: logo).resizable().scaledToFit().frame(width: 76, height: 48)
                                .accessibilityHidden(true)
                        }
                        VStack(alignment: .leading, spacing: 3) {
                            Text("MuScriptor").font(.system(size: 29, weight: .semibold))
                            Text("Independent adaptation by Pokestir").font(.system(size: 11)).foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 4)
                        Button { state.openWebGUI() } label: { HStack(spacing: 4) { Text("Open Web GUI"); Image(systemName: "arrow.up.right") } }
                            .buttonStyle(.plain).foregroundStyle(Color.accentColor).font(.caption)
                            .disabled(state.busy || state.setup)
                        Menu {
                            Button("Open Session…") { state.openSession() }
                                .disabled(state.busy || state.webURL != nil)
                            Button("Recover Last Session") {
                                if let path = state.recoveryPath { state.openSession(path: path) }
                            }.disabled(state.busy || state.webURL != nil || state.recoveryPath == nil)
                            if state.hasSession {
                                Button("Save Session…") { state.saveSession() }.disabled(state.busy || state.webURL != nil)
                            }
                            Divider()
                            Picker("Processor", selection: Binding(get: { state.selectedProcessor }, set: { state.selectProcessor($0) })) {
                                Text("Automatic").tag("auto")
                                ForEach(state.processors) { processor in Text(processor.label).tag(processor.id) }
                            }.disabled(state.busy || state.webURL != nil)
                            Button("App Information…") { state.showingAppInfo = true }
                            Button("Open Model Folder") {
                                NSWorkspace.shared.open(URL(fileURLWithPath: state.modelDirectory))
                            }.disabled(state.modelDirectory.isEmpty)
                            Divider()
                            Button("Check Export Requirements") { state.checkExports() }.disabled(state.busy || state.webURL != nil)
                            Button("Repair Dependencies…") { state.repair() }.disabled(state.busy || state.webURL != nil)
                            Button("Show Logs") { NSWorkspace.shared.open(state.logs) }
                        } label: {
                            Image(systemName: "gearshape").font(.system(size: 17)).frame(width: 24, height: 24)
                        }.menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                            .help("Sessions and app options").accessibilityLabel("Sessions and app options")
                    }
                    Text("Local audio-to-MIDI, with tempo and time-signature controls, optional quantization, and reusable sessions. Open the web GUI for sheet music and audio/MIDI preview.")
                        .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
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
                    }.pickerStyle(.segmented).labelsHidden().disabled(state.busy || state.webURL != nil)
                    Text("Small uses less memory · Medium balances size and accuracy · Large favors accuracy")
                        .font(.caption).foregroundStyle(.secondary)
                }

                if state.webURL != nil {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Web GUI running locally").font(.headline)
                        Text("Using this app’s \(state.modelName) model and \(state.backend). Keep the app open while using your browser.")
                            .font(.subheadline).foregroundStyle(.secondary)
                        Text("Web downloads use your browser’s save location. Returning to desktop stops the web GUI and any active web transcription.")
                            .font(.caption).foregroundStyle(.secondary)
                        Button("Return to Desktop") { state.returnToDesktop() }
                    }.padding(14).background(Color.primary.opacity(0.035)).cornerRadius(12)
                } else if state.busy {
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

                if state.canCancel && state.webURL == nil {
                    HStack {
                        if state.canFinish || state.finishing {
                            Button(state.finishing ? "Finishing…" : "Finish here & save MIDI") { state.finishTranscription() }
                                .disabled(state.finishing)
                                .help("Saves fully completed 5-second sections. The unfinished section is omitted.")
                        }
                        Button("Cancel operation") { state.cancelOperation() }
                    }
                    if state.canFinish {
                        Text(String(format: "%.0f seconds completed. Finish here keeps these sections and skips the rest.", state.completedSeconds))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                if (!state.setup || state.hasSession) && state.webURL == nil { transcriptionOptions }

                if let abResult = state.abResult, state.webURL == nil {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("A/B audio saved to").font(.headline)
                        pathLabel(abResult.path)
                        Button("Reveal A/B Audio in Finder") {
                            NSWorkspace.shared.activateFileViewerSelecting([abResult])
                        }
                    }
                }

                if let destination = state.destination, state.webURL == nil {
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
            }.padding(28)
        }.frame(minWidth: 560, minHeight: 560, maxHeight: .infinity)
        .onDrop(of: [UTType.fileURL], isTargeted: $hovering) { providers in
            guard !state.busy, state.webURL == nil, let provider = providers.first else { return false }
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                let url: URL?
                if let data = item as? Data { url = URL(dataRepresentation: data, relativeTo: nil) }
                else { url = item as? URL }
                if let url = url { DispatchQueue.main.async { state.convert(url) } }
            }
            return true
        }
        .sheet(isPresented: $state.showingAppInfo) {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Text("MuScriptor").font(.title2).fontWeight(.semibold)
                    Spacer()
                    Button("Done") { state.showingAppInfo = false }.keyboardShortcut(.defaultAction)
                }
                Text("Independent adaptation by Pokestir").foregroundStyle(.secondary)
                Text("\(Bundle.main.object(forInfoDictionaryKey: "CFBundleGetInfoString") as? String ?? "Version unavailable") · Build \(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—")").font(.caption)
                Divider()
                Text("Model: \(state.modelName) · \(state.cachedModels[state.selectedModel] == true ? "Downloaded" : "Download required")")
                Text("Processor: \(state.backend)")
                Picker("Use processor", selection: Binding(get: { state.selectedProcessor }, set: { state.selectProcessor($0) })) {
                    Text("Automatic").tag("auto")
                    ForEach(state.processors) { processor in Text(processor.label).tag(processor.id) }
                }.disabled(state.busy || state.webURL != nil)
                Text(state.processorDetail).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                Text("Model download folder").font(.caption).foregroundStyle(.secondary)
                pathLabel(state.modelDirectory.isEmpty ? "Available after the model is checked." : state.modelDirectory)
                Button("Open Model Folder") { NSWorkspace.shared.open(URL(fileURLWithPath: state.modelDirectory)) }.disabled(state.modelDirectory.isEmpty)
                Divider()
                Text("Audio is processed on this computer. Original MuScriptor by Kyutai and Mirelo.").font(.caption).foregroundStyle(.secondary)
            }.padding(24).frame(width: 440)
        }
        .onAppear { state.start() }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSUserInterfaceValidations {
    let state = AppState()
    var window: NSWindow!
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let menu = NSMenu()
        func section(_ title: String) -> NSMenu {
            let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            let submenu = NSMenu(title: title); item.submenu = submenu; menu.addItem(item)
            return submenu
        }
        func action(_ title: String, _ selector: Selector, _ key: String = "", in submenu: NSMenu,
                    modifiers: NSEvent.ModifierFlags = .command) {
            let item = submenu.addItem(withTitle: title, action: selector, keyEquivalent: key)
            item.target = self; item.keyEquivalentModifierMask = modifiers
        }
        let appMenu = section("MuScriptor")
        action("About MuScriptor", #selector(showAppInfo), in: appMenu)
        action("Settings…", #selector(showAppInfo), ",", in: appMenu)
        appMenu.addItem(.separator())
        action("Repair Dependencies…", #selector(repairDependencies), in: appMenu)
        action("Show Logs", #selector(showLogs), in: appMenu)
        appMenu.addItem(.separator())
        let services = NSMenu(title: "Services")
        let servicesItem = appMenu.addItem(withTitle: "Services", action: nil, keyEquivalent: "")
        servicesItem.submenu = services; NSApp.servicesMenu = services
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Hide MuScriptor", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        let hideOthers = appMenu.addItem(withTitle: "Hide Others", action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(withTitle: "Show All", action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit MuScriptor", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let file = section("File")
        action("Open Audio…", #selector(openAudio), "o", in: file)
        action("Open Session…", #selector(openSession), "o", in: file, modifiers: [.command, .shift])
        action("Recover Last Session", #selector(recoverSession), in: file)
        file.addItem(.separator())
        action("Save Session…", #selector(saveSession), "s", in: file)
        action("Save MIDI Copy…", #selector(saveMIDI), "s", in: file, modifiers: [.command, .shift])
        action("Reveal MIDI in Finder", #selector(revealMIDI), in: file)
        file.addItem(.separator())
        file.addItem(withTitle: "Close Window", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        let edit = section("Edit")
        edit.addItem(withTitle: "Undo", action: Selector(("undo:")), keyEquivalent: "z")
        let redo = edit.addItem(withTitle: "Redo", action: Selector(("redo:")), keyEquivalent: "z")
        redo.keyEquivalentModifierMask = [.command, .shift]
        edit.addItem(.separator())
        edit.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        let view = section("View")
        action("Open Web GUI ↗", #selector(openWeb), in: view)
        action("Return to Desktop", #selector(returnToDesktop), in: view)
        action("Open Model Folder", #selector(openModelFolder), in: view)
        let windows = section("Window")
        windows.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windows.addItem(withTitle: "Zoom", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")
        windows.addItem(.separator())
        windows.addItem(withTitle: "Bring All to Front", action: #selector(NSApplication.arrangeInFront(_:)), keyEquivalent: "")
        NSApp.windowsMenu = windows
        let help = section("Help")
        action("MuScriptor Help", #selector(openHelp), in: help)
        action("Check Export Requirements", #selector(checkExports), in: help)
        action("Report an Issue…", #selector(reportIssue), in: help)
        NSApp.helpMenu = help; NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: 730), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.contentMinSize = NSSize(width: 560, height: 560)
        window.setFrameAutosaveName("MuScriptorMainWindow")
        window.title = "MuScriptor Local — 1.0 Release Candidate"
        window.contentView = NSHostingView(rootView: ContentView(state: state))
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }
    @objc func showAppInfo() { window.makeKeyAndOrderFront(nil); state.showingAppInfo = true }
    @objc func openAudio() { state.choose() }
    @objc func openSession() { state.openSession() }
    @objc func recoverSession() { if let path = state.recoveryPath { state.openSession(path: path) } }
    @objc func saveSession() { state.saveSession() }
    @objc func saveMIDI() { state.save() }
    @objc func revealMIDI() { state.reveal() }
    @objc func openWeb() { state.openWebGUI() }
    @objc func returnToDesktop() { state.returnToDesktop() }
    @objc func openModelFolder() { NSWorkspace.shared.open(URL(fileURLWithPath: state.modelDirectory)) }
    @objc func checkExports() { state.checkExports() }
    @objc func openHelp() { NSWorkspace.shared.open(URL(string: "https://github.com/PokestirVGM/MuScriptor-Local#readme")!) }
    @objc func reportIssue() { NSWorkspace.shared.open(URL(string: "https://github.com/PokestirVGM/MuScriptor-Local/issues")!) }
    func validateUserInterfaceItem(_ item: NSValidatedUserInterfaceItem) -> Bool {
        let idle = !state.busy && state.webURL == nil && window.attachedSheet == nil
        switch item.action {
        case #selector(openAudio): return idle && !state.setup
        case #selector(openSession), #selector(repairDependencies), #selector(checkExports): return idle
        case #selector(recoverSession): return idle && state.recoveryPath != nil
        case #selector(saveSession): return idle && state.hasSession
        case #selector(saveMIDI): return idle && state.result != nil
        case #selector(revealMIDI): return state.result != nil
        case #selector(openWeb): return !state.busy && !state.setup && window.attachedSheet == nil
        case #selector(returnToDesktop): return state.webURL != nil && window.attachedSheet == nil
        case #selector(openModelFolder): return !state.modelDirectory.isEmpty
        case #selector(showAppInfo): return window.attachedSheet == nil
        default: return true
        }
    }
    @objc func repairDependencies() { state.repair() }
    @objc func showLogs() { NSWorkspace.shared.open(state.logs) }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply { state.confirmDiscardTiming() ? .terminateNow : .terminateCancel }
    func applicationWillTerminate(_ notification: Notification) { state.stop() }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil); return true
    }
}

let application = NSApplication.shared
let delegate = AppDelegate()
application.delegate = delegate
application.run()
