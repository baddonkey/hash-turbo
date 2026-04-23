import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Controls.impl
import QtQuick.Layouts
import QtQuick.Dialogs

Page {
    id: root
    property string loadedHashFilePath: ""
    readonly property bool busy: (verifyModel?.isVerifying ?? false) || (verifyModel?.isLoading ?? false)

    MouseArea {
        anchors.fill: parent
        visible: root.busy
        cursorShape: Qt.WaitCursor
        acceptedButtons: Qt.NoButton
    }

    Connections {
        target: verifyModel
        function onFileLoaded(content, path) {
            pasteArea.text = content
            loadedHashFilePath = path
            baseDirField.text = verifyModel.parentDir(path)
            if (!outputDirField.text) outputDirField.text = verifyModel.parentDir(path)
        }
    }

    FileDialog {
        id: hashFileDialog
        title: qsTr("Open Hash File")
        nameFilters: ["Hash files (*.sha256 *.md5 *.sha1 *.sha512)", "All files (*)"]
        onAccepted: verifyModel.loadFile(selectedFile)
    }

    FolderDialog {
        id: baseDirBrowseDialog
        title: qsTr("Select Base Directory")
        onAccepted: baseDirField.text = verifyModel.urlToPath(selectedFolder)
    }

    FolderDialog {
        id: outputDirDialog
        title: qsTr("Select Output Directory")
        onAccepted: outputDirField.text = verifyModel.urlToPath(selectedFolder)
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

        // ── Source + Input side by side ─────────────────────────
        SplitView {
            id: sourceSplit
            Layout.fillWidth: true
            Layout.preferredHeight: 200
            orientation: Qt.Horizontal

            // ── Source ────────────────────────────────────────
            GroupBox {
                SplitView.preferredWidth: sourceSplit.width / 2
                SplitView.minimumWidth: 200
                enabled: !root.busy
                title: qsTr("Source")
                label: FloatingBadge { text: parent.title }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    // Button + Drop zone row
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Button {
                            id: loadHashFileBtn
                            objectName: "loadHashFileBtn"
                            flat: true
                            enabled: !root.busy
                            onClicked: hashFileDialog.open()
                            contentItem: Row {
                                spacing: 8
                                leftPadding: 8
                                IconImage {
                                    source: "icons/hash-file.svg"
                                    sourceSize: Qt.size(20, 20)
                                    color: root.busy ? Material.hintTextColor : Material.foreground
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Label {
                                    text: qsTr("Load Hash File")
                                    color: root.busy ? Material.hintTextColor : Material.foreground
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }

                        Button {
                            flat: true
                            visible: loadedHashFilePath.length > 0
                            enabled: !root.busy
                            onClicked: verifyModel.reloadFile(loadedHashFilePath)
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Reload file from disk")
                            contentItem: IconImage {
                                source: "icons/reload.svg"
                                sourceSize: Qt.size(20, 20)
                                color: root.busy ? Material.hintTextColor : Material.foreground
                            }
                        }

                        // Drop zone
                        Pane {
                            id: dropZonePane
                            Layout.fillWidth: true
                            Layout.minimumHeight: 40
                            enabled: !root.busy
                            padding: 10
                            Material.elevation: verifyDropArea.containsDrag ? 2 : 0

                            background: Rectangle {
                                radius: 4
                                color: verifyDropArea.containsDrag
                                    ? Qt.rgba(Material.accentColor.r, Material.accentColor.g, Material.accentColor.b, 0.06)
                                    : "transparent"
                                border.color: verifyDropArea.containsDrag ? Material.accent : Material.dividerColor
                                border.width: 1
                            }

                            DropArea {
                                id: verifyDropArea
                                anchors.fill: parent
                                enabled: !root.busy
                                onEntered: function(drag) { drag.accept() }
                                onDropped: function(drop) {
                                    if (drop.hasUrls) {
                                        verifyModel.loadFile(drop.urls[0])
                                    }
                                }
                            }

                            ColumnLayout {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                spacing: 4

                                Label {
                                    Layout.alignment: Qt.AlignHCenter
                                    visible: loadedHashFilePath.length === 0
                                    text: qsTr("Drop hash file here")
                                    font.pixelSize: 12
                                    opacity: 0.35
                                }

                                Label {
                                    id: verifyFileLabel
                                    Layout.alignment: Qt.AlignHCenter
                                    visible: loadedHashFilePath.length > 0
                                    text: loadedHashFilePath.split("/").pop().split("\\").pop()
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    font.underline: verifyFileLabelMouse.containsMouse
                                    opacity: verifyFileLabelMouse.containsMouse ? 1.0 : 0.7
                                    color: verifyFileLabelMouse.containsMouse ? Material.accent : Material.foreground

                                    MouseArea {
                                        id: verifyFileLabelMouse
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        hoverEnabled: true
                                        onClicked: verifyModel.openHashFile(loadedHashFilePath)
                                    }
                                }
                            }
                        }
                    }
                    // Base dir
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        CheckBox {
                            id: customBaseCheck
                            enabled: !root.busy
                            text: qsTr("Custom base dir")
                        }

                        TextField {
                            id: baseDirField
                            Layout.fillWidth: true
                            Layout.preferredHeight: 38
                            placeholderText: customBaseCheck.checked ? "" : qsTr("Auto-detected")
                            enabled: customBaseCheck.checked && !root.busy
                            font.pixelSize: 12
                        }
                        Button {
                            text: qsTr("…")
                            flat: true
                            implicitWidth: 36
                            enabled: customBaseCheck.checked && !root.busy
                            onClicked: baseDirBrowseDialog.open()
                        }
                    }
                }
            }

            // ── Input ────────────────────────────────────────────
            GroupBox {
                SplitView.fillWidth: true
                SplitView.minimumWidth: 200
                enabled: !root.busy
                title: qsTr("Input")
                label: FloatingBadge { text: parent.title }

                ScrollView {
                    anchors.fill: parent

                    TextArea {
                        id: pasteArea
                        readOnly: true
                        enabled: !root.busy
                        placeholderText: qsTr("Paste hash entries here, or load a hash file...")
                        font.family: window.monoFont
                        font.pixelSize: 13
                        wrapMode: TextArea.NoWrap
                        background: null
                        topPadding: 0; bottomPadding: 0; leftPadding: 0
                    }
                }

                Label {
                    anchors.centerIn: parent
                    visible: verifyModel?.isLoading ?? false
                    text: "\u23f3"
                    font.pixelSize: 28
                    opacity: 0.5
                }
            }
        }

        Label {
            Layout.alignment: Qt.AlignRight
            visible: (verifyModel?.entryCount ?? 0) > 200
            text: qsTr("%1 entries loaded (showing first 200 lines)").arg(verifyModel?.entryCount ?? 0)
            font.pixelSize: 11
            opacity: 0.5
        }

        // ── Parameters + Actions row ─────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // ── Parameters ───────────────────────────────────────
            GroupBox {
                id: parametersBox
                Layout.fillWidth: true
                Layout.minimumHeight: actionsBox.implicitHeight
                enabled: !root.busy
                title: qsTr("Parameters")
                label: FloatingBadge { text: parent.title }

                ColumnLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Label {
                            text: qsTr("Output folder")
                            Layout.alignment: Qt.AlignVCenter
                        }
                        TextField {
                            id: outputDirField
                            Layout.fillWidth: true
                            Layout.preferredHeight: 38
                            placeholderText: qsTr("Defaults to hash file parent folder")
                            font.pixelSize: 12
                        }
                        Button {
                            text: qsTr("…")
                            flat: true
                            implicitWidth: 36
                            onClicked: outputDirDialog.open()
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 16
                        CheckBox {
                            id: detectNewCheck
                            text: qsTr("Detect new files")
                            checked: true
                        }
                        CheckBox {
                            id: flexibleWsCheck
                            text: qsTr("Flexible whitespace")
                            checked: true
                        }
                        CheckBox {
                            id: binaryOnlyCheck
                            text: qsTr("Binary mode only")
                            checked: true
                        }
                    }
                }
            }

            // ── Actions ──────────────────────────────────────────
            GroupBox {
                id: actionsBox
                Layout.preferredWidth: 160
                Layout.minimumHeight: parametersBox.height
                title: qsTr("Actions")
                label: FloatingBadge { text: parent.title }

                ColumnLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2

                    Button {
                        id: verifyBtn
                        objectName: "verifyBtn"
                        Layout.fillWidth: true
                        enabled: !(verifyModel?.isLoading ?? false)
                        topPadding: 0; bottomPadding: 0; implicitHeight: 36
                        text: verifyModel?.isVerifying ? qsTr("Cancel") : qsTr("Verify")
                        background: Rectangle {
                            radius: 18
                            color: verifyBtn.pressed ? Qt.darker(verifyModel?.isVerifying ? "#c62828" : "#00796B", 1.3) : (verifyModel?.isVerifying ? "#c62828" : "#00796B")
                            opacity: verifyBtn.enabled ? 1.0 : 0.4
                        }
                        contentItem: Label {
                            text: verifyBtn.text
                            color: "#ffffff"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            opacity: verifyBtn.enabled ? 1.0 : 0.6
                        }
                        onClicked: {
                            if (verifyModel.isVerifying) {
                                verifyModel.cancel()
                            } else {
                                verifyModel.verify(
                                    pasteArea.text,
                                    loadedHashFilePath,
                                    baseDirField.text,
                                    customBaseCheck.checked,
                                    outputDirField.text,
                                    detectNewCheck.checked,
                                    flexibleWsCheck.checked,
                                    binaryOnlyCheck.checked
                                )
                            }
                        }
                    }

                    Button {
                        id: verifyClearBtn
                        Layout.fillWidth: true
                        topPadding: 0; bottomPadding: 0; implicitHeight: 36
                        text: qsTr("Clear")
                        enabled: !root.busy
                        background: Rectangle {
                            radius: 18
                            color: verifyClearBtn.pressed ? Qt.darker("#455A64", 1.3) : "#455A64"
                            opacity: verifyClearBtn.enabled ? 1.0 : 0.4
                        }
                        contentItem: Label {
                            text: verifyClearBtn.text
                            color: "#ffffff"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            opacity: verifyClearBtn.enabled ? 1.0 : 0.6
                        }
                        onClicked: {
                            verifyModel.clear()
                            pasteArea.text = ""
                            baseDirField.text = ""
                            outputDirField.text = ""
                            loadedHashFilePath = ""
                            customBaseCheck.checked = false
                        }
                    }

                    Button {
                        id: openReportBtn
                        Layout.fillWidth: true
                        topPadding: 0; bottomPadding: 0; implicitHeight: 36
                        text: qsTr("Open Report")
                        enabled: (verifyModel?.canOpenReport ?? false) && !root.busy
                        background: Rectangle {
                            radius: 18
                            color: openReportBtn.pressed ? Qt.darker("#455A64", 1.3) : "#455A64"
                            opacity: openReportBtn.enabled ? 1.0 : 0.4
                        }
                        contentItem: Label {
                            text: openReportBtn.text
                            color: "#ffffff"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            opacity: openReportBtn.enabled ? 1.0 : 0.6
                        }
                        onClicked: verifyModel.openReport()
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

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    visible: verifyModel?.progressVisible ?? false

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: verifyModel?.progressLabel ?? ""
                            font.pixelSize: 11
                            font.family: window.monoFont
                            opacity: 0.7
                        }
                        Item { Layout.fillWidth: true }
                        Label {
                            visible: (verifyModel?.progressMax ?? 0) > 0
                            text: Math.round(((verifyModel?.progressValue ?? 0) / Math.max(verifyModel?.progressMax ?? 1, 1)) * 100) + "%"
                            font.pixelSize: 11
                            font.family: window.monoFont
                            opacity: 0.7
                        }
                    }

                    ProgressBar {
                        Layout.fillWidth: true
                        from: 0
                        to: verifyModel?.progressMax ?? 0
                        value: verifyModel?.progressValue ?? 0
                        indeterminate: (verifyModel?.progressMax ?? 0) === 0
                    }
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    TextArea {
                        readOnly: true
                        text: verifyModel?.logText ?? ""
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

            Terminal {
                anchors.fill: parent
                text: verifyModel?.resultText ?? ""
                autoScroll: verifyModel?.isVerifying ?? false
            }
        }
    }
    }
}
