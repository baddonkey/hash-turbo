import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material

Pane {
    id: root

    property alias text: area.text
    property alias readOnly: area.readOnly
    property bool autoScroll: false

    padding: 0
    Material.elevation: 1

    background: Rectangle {
        color: "#000000"
        radius: 4
    }

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 2

        TextArea {
            id: area
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

            onTextChanged: {
                if (root.autoScroll) {
                    cursorPosition = text.length
                }
            }
        }
    }
}
