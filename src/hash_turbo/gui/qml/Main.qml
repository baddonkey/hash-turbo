import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtWebEngine

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

    // Colours for the third-party licenses WebEngineView HTML template.
    // Use rgb() to avoid Qt's #AARRGGBB string format being misread by CSS as #RRGGBBAA.
    readonly property string _licenseLinkColor: settingsModel?.theme === "dark" ? "#64FFDA" : "#00695C"
    function _toRgb(c) {
        return "rgb(" + Math.round(c.r * 255) + "," + Math.round(c.g * 255) + "," + Math.round(c.b * 255) + ")"
    }
    readonly property string _licenseBgColor: _toRgb(Material.background)
    readonly property string _licenseTextColor: _toRgb(Material.foreground)
    readonly property string _licenseBorderColor: _toRgb(Qt.darker(Material.background, 1.4))
    readonly property string _licenseHeaderBg: _toRgb(Qt.darker(Material.background, 1.1))

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

    Dialog {
        id: thirdPartyDialog
        title: qsTr("Third-Party Licenses")
        standardButtons: Dialog.Close
        anchors.centerIn: parent
        width: Math.min(window.width * 0.85, 820)
        height: Math.min(window.height * 0.85, 640)

        ScrollView {
            id: licensesScroll
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth

            WebEngineView {
                width: licensesScroll.availableWidth
                height: Math.max(licensesScroll.height, implicitHeight)
                settings.showScrollBars: false

                property string licenseHtml: (thirdPartyLicensesHtml ?? "")
                    .split("TEXTCOLOR").join(window._licenseTextColor)
                    .split("BGCOLOR").join(window._licenseBgColor)
                    .split("LINKCOLOR").join(window._licenseLinkColor)
                    .split("BORDERCOLOR").join(window._licenseBorderColor)
                    .split("HEADERBG").join(window._licenseHeaderBg)
                    .split("CODEBG").join(window._licenseBorderColor)

                onLicenseHtmlChanged: loadHtml(licenseHtml)
                Component.onCompleted: loadHtml(licenseHtml)

                onNavigationRequested: (request) => {
                    // navigationType 0 = LinkClickedNavigation
                    if (request.navigationType === 0) {
                        Qt.openUrlExternally(request.url)
                        request.reject()
                    }
                    // all other types (OtherNavigation = loadHtml) are allowed
                }
            }
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
                text: qsTr("Third-Party &Licenses")
                onTriggered: thirdPartyDialog.open()
            }
            Action {
                text: qsTr("&About")
                onTriggered: aboutDialog.open()
            }
        }
    }
}
