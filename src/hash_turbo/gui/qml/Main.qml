import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

ApplicationWindow {
    id: window
    visible: true
    width: 1060
    height: 840
    minimumWidth: 800
    minimumHeight: 600
    title: "hash-turbo"

    // Writable from Python tests — drives tabBar.currentIndex.
    property int testTabIndex: -1
    onTestTabIndexChanged: if (testTabIndex >= 0) tabBar.currentIndex = testTabIndex

    readonly property string monoFont: Qt.platform.os === "osx" ? "Menlo" : "Consolas"

    Material.theme: {
        if (settingsModel?.theme === "dark") return Material.Dark
        if (settingsModel?.theme === "light") return Material.Light
        return Material.System
    }
    Material.accent: Material.Teal

    // True when any long-running task is active — locks the user to the current tab.
    readonly property bool taskRunning: (hashModel?.isHashing ?? false) || (verifyModel?.isVerifying ?? false) || (sanitizeModel?.isSanitizing ?? false)

    header: TabBar {
        id: tabBar
        objectName: "tabBar"
        TabButton { objectName: "tabHash";     text: qsTr("Hash");     enabled: !taskRunning || tabBar.currentIndex === 0 }
        TabButton { objectName: "tabVerify";   text: qsTr("Verify");   enabled: !taskRunning || tabBar.currentIndex === 1 }
        TabButton { objectName: "tabSanitize"; text: qsTr("Sanitize"); enabled: !taskRunning || tabBar.currentIndex === 2 }
        TabButton { objectName: "tabSettings"; text: qsTr("Settings"); enabled: !taskRunning || tabBar.currentIndex === 3 }
    }

    StackLayout {
        anchors.fill: parent
        currentIndex: tabBar.currentIndex

        HashView {}
        VerifyView {}
        SanitizeView {}
        SettingsView {}
    }

    Dialog {
        id: aboutDialog
        title: qsTr("About hash-turbo")
        standardButtons: Dialog.Ok
        anchors.centerIn: parent

        Label {
            text: "hash-turbo v" + appVersion
                  + "\n\nCross-platform file hash management tool\n"
                  + "with CLI and PySide6 GUI.\n\nLicense: MIT"
        }
    }

    menuBar: MenuBar {
        Menu {
            title: qsTr("&File")
            Action {
                text: qsTr("E&xit")
                shortcut: "Ctrl+Q"
                onTriggered: Qt.quit()
            }
        }
        Menu {
            title: qsTr("&Help")
            Action {
                text: qsTr("&User Manual")
                enabled: userManualUrl !== ""
                onTriggered: Qt.openUrlExternally(userManualUrl)
            }
            Action {
                text: qsTr("&About")
                onTriggered: aboutDialog.open()
            }
        }
    }
}
