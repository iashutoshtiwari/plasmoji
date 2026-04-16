import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: root

    width: 400
    height: 500
    visible: windowBridge.windowVisible
    title: "Plasmoji"
    color: "transparent"

    flags: Qt.FramelessWindowHint
         | Qt.WindowStaysOnTopHint
         | Qt.Tool

    // ── Bind to Controller Signals ───────────────────────────────────
    Connections {
        target: controller
        function onSearchResultsReady(query, results) {
            assetsModel.clear();
            for (let i = 0; i < results.length; ++i) {
                assetsModel.append(results[i]);
            }
        }
    }

    // Connect DBus toggle to bridge internal dismissal
    Connections {
        target: controller
        function onInjectionRequested() {
            windowBridge.dismiss();
        }
    }

    // ── Variables & Colors ───────────────────────────────────────────
    // Fetch user accent using Python controller
    property color accentColor: controller.get_kdeglobals_accent()

    // ── Window Positioning ───────────────────────────────────────────
    x: (Screen.width  - width)  / 2
    y: (Screen.height - height) / 2

    // ── State Monitoring & Focus Grabbing ────────────────────────────
    onVisibleChanged: {
        if (visible) {
            // Re-fetch color periodically on show in case user changed it
            accentColor = controller.get_kdeglobals_accent()
            // Pull initial MRU or search
            controller.search(searchField.text)
            
            // Critical Wayland focus grabbing hack
            searchField.forceActiveFocus()
        } else {
            // Clean up when hidden
            searchField.text = ""
        }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: windowBridge.dismiss()
    }

    // ── Internal Data Model ──────────────────────────────────────────
    ListModel {
        id: assetsModel
    }

    // ── Main UI Surface ──────────────────────────────────────────────
    Rectangle {
        id: backdrop
        anchors.fill: parent
        radius: 14
        color: "#1e1e2e"           // Base Fluent dark
        border.color: "#45475a"
        border.width: 1

        // Drop shadow hack
        Rectangle {
            z: -1
            anchors.fill: parent
            anchors.margins: -1
            radius: backdrop.radius + 1
            color: "transparent"
            border.color: Qt.rgba(0, 0, 0, 0.25)
            border.width: 2
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 16

            // ── Search Bar ───────────────────────────────────────────
            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: "Search emojis, kaomojis, gifs..."
                font.pixelSize: 14
                
                background: Rectangle {
                    radius: 8
                    color: "#313244"
                    border.color: searchField.activeFocus ? root.accentColor : "transparent"
                    border.width: searchField.activeFocus ? 2 : 0
                }
                
                color: "#cdd6f4"
                padding: 12

                onTextChanged: {
                    controller.search(text)
                }
            }

            // ── Main Grid ────────────────────────────────────────────
            GridView {
                id: grid
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                
                model: assetsModel
                cellWidth: 46
                cellHeight: 46
                
                delegate: Rectangle {
                    width: grid.cellWidth
                    height: grid.cellHeight
                    color: mouseArea.containsMouse ? "#313244" : "transparent"
                    radius: 8
                    
                    Text {
                        anchors.centerIn: parent
                        text: model.asset_string
                        font.pixelSize: 24
                        // For generic text that might not be full-width, wrap
                        width: parent.width - 8
                        wrapMode: Text.Wrap
                        horizontalAlignment: Text.AlignHCenter
                    }

                    MouseArea {
                        id: mouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            controller.select_asset(model.asset_string, model.id, model.type)
                        }
                    }
                }
            }
        }
    }
}
