import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Controls.impl
import QtQuick.Layouts
import QtQuick.Dialogs

Page {
    id: root
    property string loadedHashFilePath: ""
    readonly property bool busy: (sanitizeModel?.isSanitizing ?? false) || (sanitizeModel?.isLoading ?? false)

    MouseArea {
        anchors.fill: parent
        visible: root.busy
        cursorShape: Qt.WaitCursor
        acceptedButtons: Qt.NoButton
    }

    Connections {
        target: sanitizeModel
        function onFileLoaded(content, path) {
            inputArea.text = content
            loadedHashFilePath = path
            outputFileField.text = sanitizeModel.defaultOutputPath(path)
        }
    }

    FileDialog {
        id: loadDialog
        title: qsTr("Open Hash File")
        nameFilters: ["Hash files (*.sha256 *.md5 *.sha1 *.sha512)", "All files (*)"]
        onAccepted: sanitizeModel.loadFile(selectedFile)
    }

    FileDialog {
        id: outputFileDialog
        title: qsTr("Select Output File")
        fileMode: FileDialog.SaveFile
        nameFilters: ["Hash files (*.sha256 *.md5 *.sha1 *.sha512)", "All files (*)"]
        onAccepted: outputFileField.text = sanitizeModel.urlToPath(selectedFile)
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

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Button {
                            id: sanitizeLoadBtn
                            objectName: "sanitizeLoadBtn"
                            flat: true
                            enabled: !root.busy
                            onClicked: loadDialog.open()
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
                            onClicked: sanitizeModel.reloadFile(loadedHashFilePath)
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Reload file from disk")
                            contentItem: IconImage {
                                source: "icons/reload.svg"
                                sourceSize: Qt.size(20, 20)
                                color: root.busy ? Material.hintTextColor : Material.foreground
                            }
                        }

                        Pane {
                            Layout.fillWidth: true
                            Layout.minimumHeight: 40
                            padding: 10
                            Material.elevation: sanitizeDropArea.containsDrag ? 2 : 0

                            background: Rectangle {
                                radius: 4
                                color: sanitizeDropArea.containsDrag
                                    ? Qt.rgba(Material.accentColor.r, Material.accentColor.g, Material.accentColor.b, 0.06)
                                    : "transparent"
                                border.color: sanitizeDropArea.containsDrag ? Material.accent : Material.dividerColor
                                border.width: 1
                            }

                            DropArea {
                                id: sanitizeDropArea
                                anchors.fill: parent
                                enabled: !root.busy
                                onEntered: function(drag) { drag.accept() }
                                onDropped: function(drop) {
                                    if (drop.hasUrls) {
                                        sanitizeModel.loadFile(drop.urls[0])
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
                                    id: sanitizeFileLabel
                                    Layout.alignment: Qt.AlignHCenter
                                    visible: loadedHashFilePath.length > 0
                                    text: loadedHashFilePath.split("/").pop().split("\\").pop()
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    font.underline: sanitizeFileLabelMouse.containsMouse
                                    opacity: sanitizeFileLabelMouse.containsMouse ? 1.0 : 0.7
                                    color: sanitizeFileLabelMouse.containsMouse ? Material.accent : Material.foreground

                                    MouseArea {
                                        id: sanitizeFileLabelMouse
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        hoverEnabled: true
                                        onClicked: sanitizeModel.openHashFile(loadedHashFilePath)
                                    }
                                }
                            }
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
                        id: inputArea
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
                    visible: sanitizeModel?.isLoading ?? false
                    text: "\u23f3"
                    font.pixelSize: 28
                    opacity: 0.5
                }
            }
        }

        Label {
            Layout.alignment: Qt.AlignRight
            visible: (sanitizeModel?.entryCount ?? 0) > 200
            text: qsTr("%1 entries loaded (showing first 200 lines)").arg(sanitizeModel?.entryCount ?? 0)
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
                enabled: !root.busy
                title: qsTr("Parameters")
                label: FloatingBadge { text: parent.title }

                GridLayout {
                    columns: 6
                    columnSpacing: 12
                    rowSpacing: 8
                    anchors.left: parent.left
                    anchors.right: parent.right

                    Label { text: qsTr("Output format:") }
                    ComboBox {
                        id: fmtCombo
                        objectName: "fmtCombo"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        model: ListModel {
                            ListElement { text: "GNU"; value: "gnu" }
                            ListElement { text: "BSD"; value: "bsd" }
                        }
                        textRole: "text"
                        valueRole: "value"
                    }

                    Label { text: qsTr("Path separator:") }
                    ComboBox {
                        id: sepCombo
                        objectName: "sepCombo"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        model: [
                            { text: qsTr("Keep original"), value: "keep" },
                            { text: qsTr("POSIX (/)"), value: "posix" },
                            { text: qsTr("Windows (\\)"), value: "windows" }
                        ]
                        textRole: "text"
                        valueRole: "value"
                    }

                    Label { text: qsTr("Hash case:") }
                    ComboBox {
                        id: caseCombo
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        model: [
                            { text: qsTr("Keep original"), value: "keep" },
                            { text: qsTr("Lowercase"), value: "lower" },
                            { text: qsTr("Uppercase"), value: "upper" }
                        ]
                        textRole: "text"
                        valueRole: "value"
                    }

                    Label { text: qsTr("Sort:") }
                    ComboBox {
                        id: sortCombo
                        objectName: "sortCombo"
                        Layout.columnSpan: 2
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        model: [
                            { text: qsTr("None"), value: "none" },
                            { text: qsTr("By path"), value: "path" },
                            { text: qsTr("By hash"), value: "hash" },
                            { text: qsTr("Filesystem"), value: "filesystem" }
                        ]
                        textRole: "text"
                        valueRole: "value"
                    }

                    Label { text: qsTr("Line ending:") }
                    ComboBox {
                        id: endingCombo
                        Layout.columnSpan: 2
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        model: [
                            { text: qsTr("System"), value: "system" },
                            { text: qsTr("LF (Linux/macOS)"), value: "lf" },
                            { text: qsTr("CRLF (Windows)"), value: "crlf" },
                            { text: qsTr("CR (Classic Mac)"), value: "cr" }
                        ]
                        textRole: "text"
                        valueRole: "value"
                    }

                    CheckBox {
                        id: stripCheck
                        text: qsTr("Strip prefix:")
                    }
                    TextField {
                        id: prefixField
                        Layout.columnSpan: 5
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        placeholderText: "/path/to/strip"
                        enabled: stripCheck.checked
                        font.pixelSize: 12
                    }

                    CheckBox {
                        id: dedupCheck
                        Layout.columnSpan: 3
                        text: qsTr("Deduplicate")
                    }
                    CheckBox {
                        id: normalizeWsCheck
                        Layout.columnSpan: 3
                        text: qsTr("Normalize whitespace")
                        checked: true
                    }

                    Label { text: qsTr("Output file:") }
                    RowLayout {
                        Layout.columnSpan: 5
                        Layout.fillWidth: true
                        spacing: 4

                        TextField {
                            id: outputFileField
                            Layout.fillWidth: true
                            Layout.preferredHeight: 38
                            placeholderText: qsTr("Auto-filled from source file")
                            font.pixelSize: 12
                        }

                        Button {
                            flat: true
                            onClicked: outputFileDialog.open()
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Browse…")
                            contentItem: IconImage {
                                source: "icons/folder-add.svg"
                                sourceSize: Qt.size(20, 20)
                                color: Material.foreground
                            }
                        }

                        Button {
                            flat: true
                            visible: sanitizeModel?.canOpenResult ?? false
                            onClicked: sanitizeModel.openResult()
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Open output file")
                            contentItem: IconImage {
                                source: "icons/hash-file.svg"
                                sourceSize: Qt.size(20, 20)
                                color: Material.foreground
                            }
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
                        id: transformBtn
                        objectName: "transformBtn"
                        Layout.fillWidth: true
                        enabled: !(sanitizeModel?.isLoading ?? false)
                        topPadding: 0; bottomPadding: 0; implicitHeight: 36
                        text: sanitizeModel?.isSanitizing ? qsTr("Cancel") : qsTr("Transform")
                        background: Rectangle {
                            radius: 18
                            color: transformBtn.pressed ? Qt.darker(sanitizeModel?.isSanitizing ? "#c62828" : "#00796B", 1.3) : (sanitizeModel?.isSanitizing ? "#c62828" : "#00796B")
                            opacity: transformBtn.enabled ? 1.0 : 0.4
                        }
                        contentItem: Label {
                            text: transformBtn.text
                            color: "#ffffff"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            opacity: transformBtn.enabled ? 1.0 : 0.6
                        }
                        onClicked: {
                            if (sanitizeModel.isSanitizing) {
                                sanitizeModel.cancelTransform()
                            } else {
                                sanitizeModel.outputPath = outputFileField.text
                                sanitizeModel.transform(
                                    inputArea.text,
                                    fmtCombo.currentValue,
                                    sepCombo.currentValue,
                                    stripCheck.checked ? prefixField.text : "",
                                    caseCombo.currentValue,
                                    sortCombo.currentValue,
                                    dedupCheck.checked,
                                    normalizeWsCheck.checked,
                                    endingCombo.currentValue
                                )
                            }
                        }
                    }

                    Button {
                        id: sanitizeClearBtn
                        Layout.fillWidth: true
                        topPadding: 0; bottomPadding: 0; implicitHeight: 36
                        enabled: !root.busy
                        text: qsTr("Clear")
                        background: Rectangle {
                            radius: 18
                            color: sanitizeClearBtn.pressed ? Qt.darker("#455A64", 1.3) : "#455A64"
                            opacity: sanitizeClearBtn.enabled ? 1.0 : 0.4
                        }
                        contentItem: Label {
                            text: sanitizeClearBtn.text
                            color: "#ffffff"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            opacity: sanitizeClearBtn.enabled ? 1.0 : 0.6
                        }
                        onClicked: {
                            sanitizeModel.clear()
                            inputArea.text = ""
                            loadedHashFilePath = ""
                            outputFileField.text = ""
                        }
                    }
                }
            }
        }

        // ── Log ───────────────────────────────────────────────
        GroupBox {
            Layout.fillWidth: true
            Layout.preferredHeight: 62
            title: qsTr("Log")
            label: FloatingBadge { text: parent.title }

            ScrollView {
                anchors.fill: parent

                TextArea {
                    readOnly: true
                    text: sanitizeModel?.logText ?? ""
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

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Placeholder when empty
                Label {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: !(sanitizeModel?.outputText ?? "")
                    text: qsTr("Transform results will appear here…")
                    font.pixelSize: 13
                    color: "#cdd6f4"
                    opacity: 0.35
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                // Data rows
                ListView {
                    id: resultList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: !!(sanitizeModel?.outputText ?? "")
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                        contentItem: Rectangle {
                            implicitWidth: 8
                            radius: 4
                            color: parent.pressed ? "#aab0c0" : "#6c7086"
                            opacity: parent.active ? 1.0 : 0.5
                        }
                    }

                    model: {
                        let txt = sanitizeModel?.outputText ?? ""
                        if (!txt) return []
                        return txt.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
                                  .split("\n").filter(line => line.length > 0)
                    }

                    delegate: Rectangle {
                        required property string modelData
                        required property int index
                        width: resultList.width
                        height: 24
                        color: index % 2 === 0 ? "transparent" : "#0dffffff"

                        Label {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            text: modelData
                            font.family: window.monoFont
                            font.pixelSize: 13
                            color: "#cdd6f4"
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }
    }
    }
}
