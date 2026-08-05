import AppKit
import Foundation

struct ControlConfig: Decodable {
    let pythonExecutable: String
    let managerScript: String
    let repoRoot: String
    let companionPlist: String
    let origin: String
    let protonBridgeApp: String
}

struct HealthStatus: Decodable {
    let details: String
}

struct BridgeStatus: Decodable {
    let required: Bool
    let installed: Bool
    let state: String
    let label: String
    let details: String
}

struct CompanionStatus: Decodable {
    let state: String
    let stateLabel: String
    let health: HealthStatus
    let protonBridge: BridgeStatus

    enum CodingKeys: String, CodingKey {
        case state
        case stateLabel = "state_label"
        case health
        case protonBridge = "proton_bridge"
    }
}

enum ManagerResult {
    case success(Data)
    case failure(String)
}

final class ThreadwiseControlDelegate: NSObject, NSApplicationDelegate {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let menu = NSMenu()
    private var config: ControlConfig?
    private var refreshTimer: Timer?
    private var currentStatus: CompanionStatus?
    private var actionInProgress = false
    private var statusInProgress = false

    private lazy var companionStatusItem = NSMenuItem(title: "Threadwise: Checking…", action: nil, keyEquivalent: "")
    private lazy var companionDetailItem = NSMenuItem(title: "Reading the local companion status.", action: nil, keyEquivalent: "")
    private lazy var startItem = NSMenuItem(title: "Start Threadwise", action: #selector(startCompanion), keyEquivalent: "s")
    private lazy var stopItem = NSMenuItem(title: "Stop Threadwise", action: #selector(stopCompanion), keyEquivalent: "")
    private lazy var openItem = NSMenuItem(title: "Open Threadwise", action: #selector(openThreadwise), keyEquivalent: "o")
    private lazy var bridgeStatusItem = NSMenuItem(title: "Proton Mail Bridge: Checking…", action: nil, keyEquivalent: "")
    private lazy var bridgeDetailItem = NSMenuItem(title: "Checking whether Bridge is needed.", action: nil, keyEquivalent: "")
    private lazy var openBridgeItem = NSMenuItem(title: "Open Proton Mail Bridge", action: #selector(openProtonBridge), keyEquivalent: "")

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        guard loadConfig() else {
            renderConfigurationFailure()
            return
        }
        configureStatusButton()
        configureMenu()
        refreshStatus()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            self?.refreshStatus()
        }
    }

    private func loadConfig() -> Bool {
        guard
            let url = Bundle.main.url(forResource: "threadwise-control", withExtension: "json"),
            let data = try? Data(contentsOf: url),
            let decoded = try? JSONDecoder().decode(ControlConfig.self, from: data)
        else {
            return false
        }
        config = decoded
        return true
    }

    private func configureStatusButton() {
        guard let button = statusItem.button else { return }
        button.image = NSImage(systemSymbolName: "tray.full", accessibilityDescription: "Threadwise")
        button.imagePosition = .imageLeading
        button.title = "Threadwise"
        button.toolTip = "Threadwise service control"
    }

    private func configureMenu() {
        menu.autoenablesItems = false
        companionStatusItem.isEnabled = false
        companionDetailItem.isEnabled = false
        companionDetailItem.indentationLevel = 1
        bridgeStatusItem.isEnabled = false
        bridgeDetailItem.isEnabled = false
        bridgeDetailItem.indentationLevel = 1

        for item in [startItem, stopItem, openItem, openBridgeItem] {
            item.target = self
        }

        menu.addItem(companionStatusItem)
        menu.addItem(companionDetailItem)
        menu.addItem(.separator())
        menu.addItem(startItem)
        menu.addItem(stopItem)
        menu.addItem(openItem)
        menu.addItem(.separator())
        menu.addItem(bridgeStatusItem)
        menu.addItem(bridgeDetailItem)
        menu.addItem(openBridgeItem)
        menu.addItem(.separator())

        let refreshItem = NSMenuItem(title: "Refresh Status", action: #selector(refreshStatus), keyEquivalent: "r")
        refreshItem.target = self
        menu.addItem(refreshItem)

        let quitItem = NSMenuItem(title: "Quit Menu Bar Control", action: #selector(quitControl), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)
        statusItem.menu = menu
    }

    private func renderConfigurationFailure() {
        configureStatusButton()
        companionStatusItem.title = "Threadwise: Control unavailable"
        companionDetailItem.title = "Reinstall Threadwise Control to restore its configuration."
        configureMenu()
        startItem.isEnabled = false
        stopItem.isEnabled = false
        openItem.isEnabled = false
        openBridgeItem.isHidden = true
    }

    @objc private func refreshStatus() {
        guard !actionInProgress, !statusInProgress else { return }
        statusInProgress = true
        runManager(command: "status", extraArguments: ["--json"]) { [weak self] result in
            guard let self else { return }
            self.statusInProgress = false
            switch result {
            case .success(let data):
                do {
                    let status = try JSONDecoder().decode(CompanionStatus.self, from: data)
                    self.currentStatus = status
                    self.render(status)
                } catch {
                    self.renderControlError("Threadwise returned an unreadable status.")
                }
            case .failure(let message):
                self.renderControlError(message)
            }
        }
    }

    private func render(_ status: CompanionStatus) {
        companionStatusItem.title = "Threadwise: \(status.stateLabel)"
        companionStatusItem.image = stateImage(for: status.state)
        companionDetailItem.title = status.state == "stopped"
            ? "Background service is off. Start Threadwise when you want to use it."
            : shortened(status.health.details)
        startItem.isEnabled = !actionInProgress && status.state != "running"
        stopItem.isEnabled = !actionInProgress && status.state != "stopped"
        openItem.isEnabled = status.state == "running"

        bridgeStatusItem.title = "Proton Mail Bridge: \(status.protonBridge.label)"
        bridgeStatusItem.image = stateImage(for: status.protonBridge.state)
        bridgeDetailItem.title = shortened(status.protonBridge.details)
        openBridgeItem.isHidden = !status.protonBridge.required || status.protonBridge.state == "available"
        openBridgeItem.isEnabled = status.protonBridge.installed

        statusItem.button?.toolTip = "Threadwise is \(status.stateLabel.lowercased())"
    }

    private func renderControlError(_ message: String) {
        companionStatusItem.title = "Threadwise: Needs attention"
        companionStatusItem.image = stateImage(for: "needs-attention")
        companionDetailItem.title = shortened(message)
        startItem.isEnabled = true
        stopItem.isEnabled = true
        openItem.isEnabled = false
    }

    private func stateImage(for state: String) -> NSImage? {
        let symbol: String
        switch state {
        case "running", "available": symbol = "checkmark.circle.fill"
        case "stopped", "not-configured": symbol = "stop.circle"
        default: symbol = "exclamationmark.triangle.fill"
        }
        return NSImage(systemSymbolName: symbol, accessibilityDescription: state)
    }

    @objc private func startCompanion() {
        performAction(command: "start", pendingTitle: "Threadwise: Starting…")
    }

    @objc private func stopCompanion() {
        performAction(command: "stop", pendingTitle: "Threadwise: Stopping…")
    }

    private func performAction(command: String, pendingTitle: String) {
        guard !actionInProgress else { return }
        actionInProgress = true
        companionStatusItem.title = pendingTitle
        companionDetailItem.title = "Updating the local background service."
        startItem.isEnabled = false
        stopItem.isEnabled = false
        openItem.isEnabled = false
        runManager(command: command) { [weak self] result in
            guard let self else { return }
            self.actionInProgress = false
            if case .failure(let message) = result {
                self.renderControlError(message)
                return
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                self.refreshStatus()
            }
        }
    }

    private func runManager(
        command: String,
        extraArguments: [String] = [],
        completion: @escaping (ManagerResult) -> Void
    ) {
        guard let config else {
            completion(.failure("Threadwise Control is missing its configuration."))
            return
        }
        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            let output = Pipe()
            let errors = Pipe()
            process.executableURL = URL(fileURLWithPath: config.pythonExecutable)
            process.arguments = [
                config.managerScript,
                "--repo-root", config.repoRoot,
                "--plist-path", config.companionPlist,
                command,
            ] + extraArguments
            process.standardOutput = output
            process.standardError = errors
            do {
                try process.run()
                process.waitUntilExit()
                let outputData = output.fileHandleForReading.readDataToEndOfFile()
                let errorData = errors.fileHandleForReading.readDataToEndOfFile()
                DispatchQueue.main.async {
                    if process.terminationStatus == 0 {
                        completion(.success(outputData))
                    } else {
                        let message = String(data: errorData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
                        completion(.failure(message?.isEmpty == false ? message! : "Threadwise service control failed."))
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    completion(.failure("Could not run the Threadwise service controller: \(error.localizedDescription)"))
                }
            }
        }
    }

    @objc private func openThreadwise() {
        guard let config, let url = URL(string: config.origin) else { return }
        NSWorkspace.shared.open(url)
    }

    @objc private func openProtonBridge() {
        guard let config else { return }
        let url = URL(fileURLWithPath: config.protonBridgeApp)
        let launch = NSWorkspace.OpenConfiguration()
        launch.activates = true
        NSWorkspace.shared.openApplication(at: url, configuration: launch)
    }

    @objc private func quitControl() {
        NSApp.terminate(nil)
    }

    private func shortened(_ text: String) -> String {
        let singleLine = text.replacingOccurrences(of: "\n", with: " ")
        return singleLine.count > 92 ? String(singleLine.prefix(89)) + "…" : singleLine
    }
}

let application = NSApplication.shared
let delegate = ThreadwiseControlDelegate()
application.delegate = delegate
application.run()
