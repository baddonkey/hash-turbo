import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Controls.impl
import QtQuick.Layouts
import QtQuick.Dialogs

Page {
    id: root

    readonly property int labelColumnWidth: 72
    readonly property bool compactMode: width < 700
    readonly property bool busy: hashModel?.isHashing ?? false

    FileDialog {
        id: fileDialog
        title: qsTr("Select Files")
        fileMode: FileDialog.OpenFiles
        onAccepted: hashModel.addFiles(selectedFiles)
    }

    FolderDialog {
        id: folderDialog
        title: qsTr("Select Folder")
        onAccepted: hashModel.addFolder(selectedFolder)
    }

    FileDialog {
        id: outputDialog
        title: qsTr("Output Hash File")
        fileMode: FileDialog.SaveFile
        nameFilters: [algoCombo.currentText.toUpperCase() + " files (*." + algoCombo.currentText + ")", "All files (*)"]
        onAccepted: outputField.text = hashModel.urlToPath(selectedFile)
    }

    FolderDialog {
        id: baseDirDialog
        title: qsTr("Select Base Directory")
        onAccepted: baseDirField.text = hashModel.urlToPath(selectedFolder)
    }

    Connections {
        target: hashModel
        function onFolderSelected(path) {
            if (!baseDirField.text) baseDirField.text = path
            if (!outputField.text) outputField.text = path + "/checksums." + algoCombo.currentText
        }
        function onFilesAdded(parentDir) {
            if (!baseDirField.text) baseDirField.text = parentDir
        }
    }

    Flickable {
        id: flickable
        anchors.fill: parent
        anchors.margins: 16
        contentHeight: contentColumn.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { id: vbar; policy: ScrollBar.AsNeeded }

    ColumnLayout {
        id: contentColumn
        width: flickable.width - (vbar.visible ? vbar.width : 0)
        height: Math.max(implicitHeight, flickable.height)
        spacing: 12

        // ── Source ────────────────────────────────────────────────
        GroupBox {
            Layout.fillWidth: true
            enabled: !root.busy
            title: qsTr("Source")
            label: FloatingBadge { text: parent.title }

            ColumnLayout {
                anchors.left: parent.left
                anchors.right: parent.right
                spacing: 8

                // Buttons + Drop zone row
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    // Left column (20%): buttons stacked vertically, top-aligned
                    ColumnLayout {
                        Layout.preferredWidth: 140
                        Layout.minimumWidth: 120
                        Layout.maximumWidth: 180
                        Layout.fillHeight: true
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 4

                        Button {
                            Layout.fillWidth: true
                            flat: true
                            onClicked: fileDialog.open()
                            contentItem: Row {
                                spacing: 8
                                leftPadding: 8
                                IconImage {
                                    source: "icons/file-add.svg"
                                    sourceSize: Qt.size(20, 20)
                                    color: Material.foreground
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Label {
                                    text: qsTr("Add Files")
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                        Button {
                            id: addFolderBtn
                            objectName: "addFolderBtn"
                            Layout.fillWidth: true
                            flat: true
                            onClicked: folderDialog.open()
                            contentItem: Row {
                                spacing: 8
                                leftPadding: 8
                                IconImage {
                                    source: "icons/folder-add.svg"
                                    sourceSize: Qt.size(20, 20)
                                    color: Material.foreground
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Label {
                                    text: qsTr("Add Folder")
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                    }

                    // Right column (80%): drop zone
                    Pane {
                        Layout.fillWidth: true
                        Layout.minimumHeight: 112
                        Layout.maximumHeight: 200
                        padding: 10
                        clip: true
                        Material.elevation: dropArea.containsDrag ? 2 : 0

                        background: Rectangle {
                            radius: 4
                            color: dropArea.containsDrag
                                ? Qt.rgba(Material.accentColor.r, Material.accentColor.g, Material.accentColor.b, 0.06)
                                : "transparent"
                            border.color: dropArea.containsDrag ? Material.accent : Material.dividerColor
                            border.width: 1
                        }

                        DropArea {
                            id: dropArea
                            anchors.fill: parent
                            onEntered: function(drag) { drag.accept() }
                            onDropped: function(drop) {
                                if (drop.hasUrls) hashModel.addFiles(drop.urls)
                            }
                        }

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 4

                            // Empty hint
                            Label {
                                Layout.alignment: Qt.AlignHCenter
                                visible: (hashModel?.pendingCount ?? 0) === 0
                                text: qsTr("Drop files or folders here")
                                font.pixelSize: 12
                                opacity: 0.35
                            }

                            // Pending header
                            Label {
                                visible: (hashModel?.pendingCount ?? 0) > 0
                                text: qsTr("%1 item(s)").arg(hashModel?.pendingCount ?? 0)
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                opacity: 0.55
                            }

                            // Pending list
                            ScrollView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                visible: (hashModel?.pendingCount ?? 0) > 0
                                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                                TextArea {
                                    readOnly: true
                                    text: hashModel?.pendingDisplay ?? ""
                                    font.pixelSize: 11
                                    font.family: window.monoFont
                                    wrapMode: TextArea.NoWrap
                                    background: null
                                    topPadding: 0; bottomPadding: 0; leftPadding: 0
                                }
                            }
                        }
                    }
                }

                // Base dir — aligned with drop zone above
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    // Left spacer matching button column width
                    RowLayout {
                        Layout.preferredWidth: 140
                        Layout.minimumWidth: 120
                        Layout.maximumWidth: 180
                        spacing: 2

                        CheckBox {
                            id: relativeCheck
                            text: qsTr("Relative paths")
                            checked: true
                        }
                    }

                    // Right side — aligned with drop zone
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Label {
                            text: qsTr("Base dir")
                            Layout.alignment: Qt.AlignVCenter
                            enabled: relativeCheck.checked
                            opacity: relativeCheck.checked ? 1.0 : 0.4
                        }
                        TextField {
                            id: baseDirField
                            Layout.fillWidth: true
                            Layout.preferredHeight: 38
                            placeholderText: qsTr("Auto-detected")
                            enabled: relativeCheck.checked
                            font.pixelSize: 12
                        }
                        Button {
                            text: qsTr("…")
                            flat: true
                            implicitWidth: 36
                            enabled: relativeCheck.checked
                            onClicked: baseDirDialog.open()
                        }
                        CheckBox {
                            id: recursiveCheck
                            text: qsTr("Recursive")
                            checked: true
                        }
                    }
                }
            }
        }

        // ── Parameters + Actions row ─────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // ── Parameters ───────────────────────────────────────
            GroupBox {
                id: parametersBox
                Layout.fillWidth: true
                enabled: !root.busy
                title: qsTr("Parameters")
                label: FloatingBadge { text: parent.title }

                ColumnLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 6

                    // Algorithm + Format
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Label {
                            text: qsTr("Algorithm")
                            Layout.preferredWidth: root.labelColumnWidth
                            Layout.alignment: Qt.AlignVCenter
                        }
                        ComboBox {
                            id: algoCombo
                            Layout.fillWidth: true
                            Layout.preferredHeight: 38
                            model: ["sha256", "sha1", "md5", "sha224", "sha384", "sha512",
                                    "sha3-256", "sha3-512", "blake2b", "blake2s"]
                            Component.onCompleted: {
                                var idx = model.indexOf(settingsModel.defaultAlgorithm)
                                if (idx >= 0) currentIndex = idx
                            }
                            onCurrentTextChanged: {
                                if (outputField.text) {
                                    var lastDot = outputField.text.lastIndexOf(".")
                                    if (lastDot > 0) {
                                        outputField.text = outputField.text.substring(0, lastDot + 1) + currentText
                                    }
                                }
                            }
                        }
                        Label {
                            text: qsTr("Format")
                            Layout.alignment: Qt.AlignVCenter
                        }
                        ComboBox {
                            id: fmtCombo
                            Layout.fillWidth: true
                            Layout.preferredHeight: 38
                            model: ListModel {
                                ListElement { text: "GNU"; value: "gnu" }
                                ListElement { text: "BSD"; value: "bsd" }
                            }
                            textRole: "text"
                            valueRole: "value"
                            Component.onCompleted: {
                                for (var i = 0; i < model.count; i++) {
                                    if (model.get(i).value === settingsModel.outputFormat) {
                                        currentIndex = i
                                        break
                                    }
                                }
                            }
                        }
                    }

                    // Output file
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Label {
                            text: qsTr("Output")
                            Layout.preferredWidth: root.labelColumnWidth
                            Layout.alignment: Qt.AlignVCenter
                        }
                        TextField {
                            id: outputField
                            Layout.fillWidth: true
                            Layout.preferredHeight: 38
                            placeholderText: "checksums." + algoCombo.currentText
                            font.pixelSize: 12
                        }
                        Button {
                            text: qsTr("…")
                            flat: true
                            implicitWidth: 36
                            onClicked: outputDialog.open()
                        }
                        Button {
                            text: qsTr("Open")
                            flat: true
                            enabled: hashModel?.canOpenOutput ?? false
                            onClicked: hashModel.openOutput(outputField.text)
                        }
                    }
                }
            }

            // ── Actions ──────────────────────────────────────────
            GroupBox {
                Layout.preferredWidth: 160
                Layout.preferredHeight: parametersBox.height
                title: qsTr("Actions")
                label: FloatingBadge { text: parent.title }

                ColumnLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2

                    Button {
                        id: hashBtn
                        objectName: "hashBtn"
                        Layout.fillWidth: true
                        topPadding: 0; bottomPadding: 0; implicitHeight: 36
                        text: hashModel?.isHashing ? qsTr("Cancel") : qsTr("Hash")
                        enabled: hashModel?.isHashing || (hashModel?.pendingCount ?? 0) > 0
                        icon.name: hashModel?.isHashing ? "process-stop" : ""
                        background: Rectangle {
                            radius: 18
                            color: hashBtn.pressed ? Qt.darker(hashModel?.isHashing ? "#c62828" : "#00796B", 1.3) : (hashModel?.isHashing ? "#c62828" : "#00796B")
                            opacity: hashBtn.enabled ? 1.0 : 0.4
                        }
                        contentItem: Label {
                            text: hashBtn.text
                            color: "#ffffff"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            opacity: hashBtn.enabled ? 1.0 : 0.6
                        }
                        onClicked: {
                            if (hashModel.isHashing) {
                                hashModel.cancelHash()
                            } else {
                                hashModel.startHash(
                                    algoCombo.currentText,
                                    fmtCombo.currentValue,
                                    recursiveCheck.checked,
                                    relativeCheck.checked,
                                    baseDirField.text,
                                    outputField.text
                                )
                            }
                        }
                    }

                    Button {
                        id: clearBtn
                        Layout.fillWidth: true
                        topPadding: 0; bottomPadding: 0; implicitHeight: 36
                        text: qsTr("Clear")
                        enabled: (hashModel?.pendingCount ?? 0) > 0 && !(hashModel?.isHashing ?? false)
                        background: Rectangle {
                            radius: 18
                            color: clearBtn.pressed ? Qt.darker("#455A64", 1.3) : "#455A64"
                            opacity: clearBtn.enabled ? 1.0 : 0.4
                        }
                        contentItem: Label {
                            text: clearBtn.text
                            color: "#ffffff"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            opacity: clearBtn.enabled ? 1.0 : 0.6
                        }
                        onClicked: {
                            hashModel.clear()
                            baseDirField.text = ""
                            outputField.text = ""
                        }
                    }
                }
            }
        }

        // ── Log ──────────────────────────────────────────────────
        GroupBox {
            Layout.fillWidth: true
            Layout.preferredHeight: 100
            title: qsTr("Log")
            label: FloatingBadge { text: parent.title }

            ColumnLayout {
                anchors.fill: parent
                spacing: 4

                // Progress bar
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    visible: hashModel?.progressVisible ?? false

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: hashModel?.progressLabel ?? ""
                            font.pixelSize: 11
                            font.family: window.monoFont
                            opacity: 0.7
                        }
                        Item { Layout.fillWidth: true }
                        Label {
                            visible: (hashModel?.progressMax ?? 0) > 0
                            text: Math.round(((hashModel?.progressValue ?? 0) / Math.max(hashModel?.progressMax ?? 1, 1)) * 100) + "%"
                            font.pixelSize: 11
                            font.family: window.monoFont
                            opacity: 0.7
                        }
                    }

                    ProgressBar {
                        Layout.fillWidth: true
                        from: 0
                        to: hashModel?.progressMax ?? 0
                        value: hashModel?.progressValue ?? 0
                        indeterminate: (hashModel?.progressMax ?? 0) === 0
                    }
                }

                // Log text
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    TextArea {
                        id: logArea
                        readOnly: true
                        text: hashModel?.logText ?? ""
                        font.pixelSize: 12
                        font.family: window.monoFont
                        wrapMode: TextArea.NoWrap
                        background: null
                        topPadding: 0; bottomPadding: 0; implicitHeight: 36; leftPadding: 0
                        opacity: 0.7

                        onTextChanged: {
                            cursorPosition = text.length
                        }
                    }
                }
            }
        }

        // ── Result ───────────────────────────────────────────────
        GroupBox {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 150
            implicitHeight: Layout.minimumHeight
            title: qsTr("Result")
            label: FloatingBadge { text: parent.title }

            background: Rectangle {
                color: "#000000"
                radius: 4
                y: parent.topPadding
                height: parent.availableHeight
            }

            Pane {
                anchors.fill: parent
                padding: 0

                background: Rectangle {
                    color: "#000000"
                }

                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 2

                    TextArea {
                        id: resultArea
                        readOnly: true
                        font.family: window.monoFont
                        font.pixelSize: 13
                        color: "#cdd6f4"
                        selectionColor: "#45475a"
                        selectedTextColor: "#cdd6f4"
                        wrapMode: TextArea.NoWrap
                        background: null
                        leftPadding: 8
                        topPadding: 8

                        // Rolling output — keep last 200 lines
                        property string fullText: hashModel?.resultText ?? ""
                        onFullTextChanged: {
                            var lines = fullText.split("\n")
                            if (lines.length > 200) {
                                text = lines.slice(lines.length - 200).join("\n")
                            } else {
                                text = fullText
                            }
                            cursorPosition = text.length
                        }
                    }
                }
            }
        }
    }
    }
}
