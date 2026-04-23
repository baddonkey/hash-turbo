import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Page {
    id: root

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16

        ColumnLayout {
            width: root.width - 32
            spacing: 12

            GroupBox {
                title: qsTr("Defaults")
                Layout.fillWidth: true
                label: FloatingBadge { text: parent.title }

                GridLayout {
                    columns: 2
                    columnSpacing: 12
                    rowSpacing: 8

                    Label { text: qsTr("Default Algorithm:") }
                    ComboBox {
                        id: algoCombo
                        Layout.preferredHeight: 38
                        property bool ready: false
                        model: ["sha256", "sha1", "md5", "sha224", "sha384", "sha512",
                                "sha3-256", "sha3-512", "blake2b", "blake2s"]
                        Component.onCompleted: {
                            currentIndex = model.indexOf(settingsModel.defaultAlgorithm)
                            ready = true
                        }
                        onCurrentTextChanged: {
                            if (ready) settingsModel.defaultAlgorithm = currentText
                        }
                    }

                    Label { text: qsTr("Path Mode:") }
                    ComboBox {
                        id: pathCombo
                        Layout.preferredHeight: 38
                        property bool ready: false
                        model: ["relative", "absolute"]
                        Component.onCompleted: {
                            currentIndex = model.indexOf(settingsModel.pathMode)
                            ready = true
                        }
                        onCurrentTextChanged: {
                            if (ready) settingsModel.pathMode = currentText
                        }
                    }

                    Label { text: qsTr("Output Format:") }
                    ComboBox {
                        id: fmtCombo
                        Layout.preferredHeight: 38
                        property bool ready: false
                        model: ["gnu", "bsd", "json"]
                        Component.onCompleted: {
                            currentIndex = model.indexOf(settingsModel.outputFormat)
                            ready = true
                        }
                        onCurrentTextChanged: {
                            if (ready) settingsModel.outputFormat = currentText
                        }
                    }
                }
            }

            GroupBox {
                title: qsTr("Appearance")
                Layout.fillWidth: true
                label: FloatingBadge { text: parent.title }

                GridLayout {
                    columns: 2
                    columnSpacing: 12

                    Label { text: qsTr("Theme:") }
                    ComboBox {
                        id: themeCombo
                        objectName: "themeCombo"
                        Layout.preferredHeight: 38
                        property bool ready: false
                        model: ["system", "light", "dark"]
                        Component.onCompleted: {
                            currentIndex = model.indexOf(settingsModel.theme)
                            ready = true
                        }
                        onCurrentTextChanged: {
                            if (ready) settingsModel.theme = currentText
                        }
                    }
                }
            }

            GroupBox {
                title: qsTr("Language")
                Layout.fillWidth: true
                label: FloatingBadge { text: parent.title }

                ColumnLayout {
                    spacing: 8

                    ComboBox {
                        id: langCombo
                        Layout.preferredHeight: 38
                        model: settingsModel?.languageNames ?? []
                        property bool ready: false
                        Component.onCompleted: {
                            var codes = settingsModel.languageCodes
                            var idx = codes.indexOf(settingsModel.language)
                            if (idx >= 0) currentIndex = idx
                            ready = true
                        }
                        onCurrentIndexChanged: {
                            if (!ready || !settingsModel) return
                            var codes = settingsModel.languageCodes
                            if (currentIndex >= 0 && currentIndex < codes.length) {
                                settingsModel.language = codes[currentIndex]
                            }
                        }
                    }

                    Label {
                        text: qsTr("Restart the application for language changes to take full effect.")
                        font.italic: true
                        font.pixelSize: 12
                    }
                }
            }

            GroupBox {
                title: qsTr("Exclude Patterns")
                Layout.fillWidth: true
                label: FloatingBadge { text: parent.title }

                ColumnLayout {
                    spacing: 8
                    Layout.fillWidth: true

                    Label { text: qsTr("One pattern per line. Prefix with re: for regex.") }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 120
                        color: "transparent"
                        border.color: Material.hintTextColor
                        border.width: 1
                        radius: 4
                        clip: true

                        ScrollView {
                            anchors.fill: parent
                            anchors.margins: 1

                            TextArea {
                                background: null
                                text: settingsModel?.excludePatterns ?? ""
                                onTextChanged: if (settingsModel) settingsModel.excludePatterns = text
                            }
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
