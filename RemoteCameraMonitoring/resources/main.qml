import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: window
    width: 1000
    height: 650
    visible: true
    title: "RemoteCamera // Server Launcher"
    color: "#0a0c0e"

    // Custom Font definitions
    font.family: "Segoe UI, Helvetica, Arial, sans-serif"
    font.pixelSize: 13

    // State Colors
    readonly property color bgDark: "#0a0c0e"
    readonly property color panelBg: "#111417"
    readonly property color borderDark: "#1e2329"
    readonly property color greenAccent: "#00e676"
    readonly property color redAccent: "#ff3d3d"
    readonly property color orangeAccent: "#ffa726"
    readonly property color textLight: "#c8cdd4"
    readonly property color textDim: "#4a5060"
    readonly property color inputBg: "#16191f"

    ListModel {
        id: logModel
    }

    Connections {
        target: backend
        function onLogReceived(text, tag) {
            var color = "#c8cdd4"
            if (tag === "ok") color = "#00e676"
            else if (tag === "err") color = "#ff3d3d"
            else if (tag === "warn") color = "#ffa726"
            else if (tag === "info") color = "#4a5060"

            logModel.append({
                "logText": text,
                "logColor": color
            })
            if (logModel.count > 1000) {
                logModel.remove(0)
            }
            logListView.positionViewAtEnd()
        }
    }

    // Main Layout container
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Header Bar
        Rectangle {
            Layout.fillWidth: true
            height: 50
            color: "#111417"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                spacing: 12

                Text {
                    text: "RemoteCamera"
                    font.bold: true
                    font.pixelSize: 16
                    color: "#00e676"
                }

                Text {
                    text: "// SERVER LAUNCHER"
                    font.pixelSize: 11
                    font.bold: true
                    color: "#4a5060"
                }

                Item { Layout.fillWidth: true }

                // Quick Status Indicator
                Rectangle {
                    width: 12
                    height: 12
                    radius: 6
                    color: backend ? backend.statusColor : "#4a5060"

                    // Subtle breathing/pulsing animation when running
                    SequentialAnimation on opacity {
                        running: backend ? backend.isRunning : false
                        loops: Animation.Infinite
                        PropertyAnimation { to: 0.4; duration: 800; easing.type: Easing.InOutQuad }
                        PropertyAnimation { to: 1.0; duration: 800; easing.type: Easing.InOutQuad }
                    }
                }

                Text {
                    text: backend ? backend.statusText.toUpperCase() : ""
                    font.bold: true
                    font.pixelSize: 11
                    color: backend ? backend.statusColor : "#4a5060"
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: "#1e2329"
            }
        }

        // Body Content (Settings & Terminal Console)
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Settings Left Panel
            ScrollView {
                id: settingsScrollView
                Layout.preferredWidth: 420
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    // Width must be explicit for ScrollView to know its content width.
                    // Subtract 28px (14px each side) to give cards breathing room.
                    width: settingsScrollView.width - 28
                    x: 14   // left inset
                    spacing: 16
                    // Top gap
                    Item { Layout.preferredHeight: 4 }

                    // Basic Settings Card
                    SettingsCard {
                        title: "BASIC CONFIGURATION"

                        ColumnLayout {
                            width: parent.width
                            spacing: 10

                            RowLayout {
                                spacing: 10
                                Text { text: "Camera"; font.bold: true; color: "#4a5060"; Layout.preferredWidth: 90 }
                                StyledComboBox {
                                    model: backend.cameras
                                    Layout.fillWidth: true
                                    currentIndex: model.indexOf(backend.selectedCamera)
                                    onActivated: (index) => backend.selectedCamera = model[index]
                                }
                            }

                            RowLayout {
                                spacing: 10
                                Text { text: "Width (px)"; font.bold: true; color: "#4a5060"; Layout.preferredWidth: 90 }
                                StyledTextField {
                                    text: backend.streamWidth
                                    Layout.fillWidth: true
                                    onTextChanged: backend.streamWidth = text
                                    validator: IntValidator { bottom: 1; top: 9999 }
                                }
                                Text { text: "Height"; font.bold: true; color: "#4a5060" }
                                StyledTextField {
                                    text: backend.streamHeight
                                    Layout.fillWidth: true
                                    onTextChanged: backend.streamHeight = text
                                    validator: IntValidator { bottom: 1; top: 9999 }
                                }
                            }

                            RowLayout {
                                spacing: 10
                                Text { text: "FPS"; font.bold: true; color: "#4a5060"; Layout.preferredWidth: 90 }
                                StyledTextField {
                                    text: backend.fps
                                    Layout.fillWidth: true
                                    onTextChanged: backend.fps = text
                                    validator: IntValidator { bottom: 1; top: 120 }
                                }
                                Text { text: "Port  "; font.bold: true; color: "#4a5060" }
                                StyledTextField {
                                    text: backend.port
                                    Layout.fillWidth: true
                                    onTextChanged: backend.port = text
                                    validator: IntValidator { bottom: 1; top: 65535 }
                                }
                            }
                        }
                    }

                    // Security Card
                    SettingsCard {
                        title: "SECURITY CREDENTIALS"

                        ColumnLayout {
                            width: parent.width
                            spacing: 10

                            RowLayout {
                                spacing: 10
                                Text { text: "Password"; font.bold: true; color: "#4a5060"; Layout.preferredWidth: 90 }
                                StyledTextField {
                                    text: backend.password
                                    echoMode: TextInput.Password
                                    placeholderText: "Leave empty for none"
                                    Layout.fillWidth: true
                                    onTextChanged: backend.password = text
                                }
                                
                                StyledButton {
                                    text: "Hash"
                                    Layout.preferredWidth: 70
                                    onClicked: backend.generateHash()
                                }
                            }

                            RowLayout {
                                spacing: 10
                                Text { text: "Hash"; font.bold: true; color: "#4a5060"; Layout.preferredWidth: 90 }
                                StyledTextField {
                                    text: backend.passwordHash
                                    placeholderText: "Configured PBKDF2 hash"
                                    Layout.fillWidth: true
                                    onTextChanged: backend.passwordHash = text
                                }
                            }

                            Text {
                                text: "Remote HTTPS / TLS private key files:"
                                font.pixelSize: 11
                                font.bold: true
                                color: "#4a5060"
                                Layout.topMargin: 4
                            }

                            RowLayout {
                                spacing: 10
                                StyledButton {
                                    text: "Cert File"
                                    Layout.preferredWidth: 100
                                    onClicked: backend.selectCertFile()
                                }
                                Text {
                                    text: backend.sslCert ? backend.sslCert.substring(backend.sslCert.lastIndexOf('/') + 1) : "No cert selected"
                                    color: backend.sslCert ? "#c8cdd4" : "#4a5060"
                                    elide: Text.ElideLeft
                                    font.italic: !backend.sslCert
                                    Layout.fillWidth: true
                                }
                            }

                            RowLayout {
                                spacing: 10
                                StyledButton {
                                    text: "Key File"
                                    Layout.preferredWidth: 100
                                    onClicked: backend.selectKeyFile()
                                }
                                Text {
                                    text: backend.sslKey ? backend.sslKey.substring(backend.sslKey.lastIndexOf('/') + 1) : "No key selected"
                                    color: backend.sslKey ? "#c8cdd4" : "#4a5060"
                                    elide: Text.ElideLeft
                                    font.italic: !backend.sslKey
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }

                    // Audio Card
                    SettingsCard {
                        title: "AUDIO SETTINGS"

                        ColumnLayout {
                            width: parent.width
                            spacing: 10

                            RowLayout {
                                spacing: 10
                                Text { text: "Device"; font.bold: true; color: "#4a5060"; Layout.preferredWidth: 90 }
                                StyledComboBox {
                                    model: backend.audioDevices
                                    Layout.fillWidth: true
                                    currentIndex: model.indexOf(backend.selectedAudio)
                                    onActivated: (index) => backend.selectedAudio = model[index]
                                }
                            }
                        }
                    }

                    // Features Card
                    SettingsCard {
                        title: "FEATURE TOGGLES"

                        ColumnLayout {
                            width: parent.width
                            spacing: 8

                            StyledCheckBox {
                                text: "Enable motion detection"
                                checked: backend.motion
                                onCheckedChanged: backend.motion = checked
                            }

                            StyledCheckBox {
                                text: "Enable video recordings"
                                checked: backend.recordings
                                onCheckedChanged: backend.recordings = checked
                            }

                            StyledCheckBox {
                                text: "Enable HTTPS with Caddy reverse proxy"
                                checked: backend.caddy
                                onCheckedChanged: backend.caddy = checked
                            }
                        }
                    }

                    // Launcher Controls
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 8
                        spacing: 12

                        StyledButton {
                            id: runBtn
                            text: (backend && backend.isRunning) ? "■   STOP SERVER" : "▶   START SERVER"
                            font.bold: true
                            Layout.fillWidth: true
                            Layout.preferredHeight: 45
                            customBgColor: (backend && backend.isRunning) ? "#ff3d3d" : "#00e676"
                            customTextColor: "#0a0c0e"

                            // Glowing pulsing effect on start button
                            Rectangle {
                                anchors.fill: parent
                                radius: parent.background.radius
                                color: parent.customBgColor
                                opacity: 0.15
                                scale: 1.04
                                z: -1
                                visible: backend ? !backend.isRunning : true
                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite
                                    PropertyAnimation { to: 0.02; duration: 1200; easing.type: Easing.InOutQuad }
                                    PropertyAnimation { to: 0.25; duration: 1200; easing.type: Easing.InOutQuad }
                                }
                            }

                            onClicked: backend.toggleServer()
                        }

                        StyledButton {
                            text: "🌐"
                            font.pixelSize: 18
                            Layout.preferredWidth: 50
                            Layout.preferredHeight: 45
                            customBgColor: "#111417"
                            customTextColor: "#00e676"
                            customBorderColor: "#1e2329"
                            onClicked: backend.openBrowser()
                        }
                    }
                    Item { Layout.preferredHeight: 8 }  // bottom gap
                }
            }

            // Divider border
            Rectangle {
                Layout.fillHeight: true
                width: 1
                color: "#1e2329"
            }

            // Terminal / Console Right Panel
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // Console Header
                Rectangle {
                    Layout.fillWidth: true
                    height: 40
                    color: "#0a0c0e"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16

                        Text {
                            text: "LIVE CONSOLE LOG"
                            font.pixelSize: 11
                            font.bold: true
                            color: "#4a5060"
                        }

                        Item { Layout.fillWidth: true }

                        StyledButton {
                            text: "CLEAR"
                            font.pixelSize: 10
                            Layout.preferredHeight: 24
                            Layout.preferredWidth: 60
                            customBgColor: "transparent"
                            customTextColor: "#4a5060"
                            customBorderColor: "#1e2329"
                            onClicked: logModel.clear()
                        }
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: "#1e2329"
                    }
                }

                // Console terminal scrolling view
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#050709"

                    ListView {
                        id: logListView
                        anchors.fill: parent
                        anchors.margins: 12
                        clip: true
                        model: logModel
                        spacing: 4

                        delegate: Item {
                            width: logListView.width
                            height: logTextElement.implicitHeight

                            Text {
                                id: logTextElement
                                width: parent.width - 20
                                text: logText
                                color: logColor
                                wrapMode: Text.WrapAnywhere
                                font.family: "Consolas, Courier New, monospace"
                                font.pixelSize: 11
                            }
                        }

                        // Custom Scrollbar
                        ScrollBar.vertical: ScrollBar {
                            active: true
                            policy: ScrollBar.AlwaysOn
                            contentItem: Rectangle {
                                implicitWidth: 6
                                radius: 3
                                color: "#1e2329"
                            }
                            background: Rectangle {
                                color: "transparent"
                            }
                        }
                    }
                }
            }
        }
    }

    // --- Custom Components ---

    // Settings Card Container
    component SettingsCard: Rectangle {
        property string title: ""
        default property alias content: innerContent.data

        // Derive height from the actual outer layout so nothing overflows.
        // The outer ColumnLayout uses anchors.fill, so its implicitHeight
        // already includes the title, separator, spacing and all margins.
        Layout.fillWidth: true
        implicitHeight: cardLayout.implicitHeight + cardLayout.anchors.topMargin + cardLayout.anchors.bottomMargin
        radius: 6
        color: "#111417"
        border.color: "#1e2329"
        border.width: 1

        ColumnLayout {
            id: cardLayout
            // Use explicit anchors with margins so implicitHeight is reliable
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.topMargin: 14
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            anchors.bottomMargin: 14
            spacing: 10

            Text {
                text: title
                font.bold: true
                font.pixelSize: 10
                color: "#4a5060"
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1e2329"
            }

            ColumnLayout {
                id: innerContent
                Layout.fillWidth: true
                spacing: 10
            }
        }
    }

    // Styled Inputs (TextField)
    component StyledTextField: TextField {
        id: rootText
        color: "#c8cdd4"
        font.pixelSize: 12
        verticalAlignment: TextInput.AlignVCenter
        selectByMouse: true
        leftPadding: 10
        rightPadding: 10
        topPadding: 6
        bottomPadding: 6

        background: Rectangle {
            color: "#16191f"
            border.color: rootText.activeFocus ? "#00e676" : "#1e2329"
            border.width: 1
            radius: 4
        }
        
        placeholderTextColor: "#4a5060"
    }

    // Styled Dropdown (ComboBox)
    component StyledComboBox: ComboBox {
        id: rootCombo
        font.pixelSize: 12

        delegate: ItemDelegate {
            width: rootCombo.width
            contentItem: Text {
                text: modelData
                color: highlighted ? "#00e676" : "#c8cdd4"
                font: rootCombo.font
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                color: highlighted ? "#1b2026" : "#111417"
            }
        }

        indicator: Canvas {
            id: canvas
            x: rootCombo.width - width - rootCombo.rightPadding
            y: rootCombo.topPadding + (rootCombo.availableHeight - height) / 2
            width: 10
            height: 7
            contextType: "2d"

            onPaint: {
                context.reset();
                context.moveTo(0, 0);
                context.lineTo(width, 0);
                context.lineTo(width / 2, height);
                context.closePath();
                context.fillStyle = "#c8cdd4";
                context.fill();
            }
        }

        contentItem: Text {
            leftPadding: 10
            rightPadding: rootCombo.indicator.width + rootCombo.spacing
            text: rootCombo.displayText
            font: rootCombo.font
            color: "#c8cdd4"
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        background: Rectangle {
            implicitWidth: 120
            implicitHeight: 30
            color: "#16191f"
            border.color: rootCombo.activeFocus ? "#00e676" : "#1e2329"
            border.width: 1
            radius: 4
        }

        popup: Popup {
            y: rootCombo.height - 1
            width: rootCombo.width
            implicitHeight: contentItem.implicitHeight
            padding: 1

            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight > 200 ? 200 : contentHeight
                model: rootCombo.popup.visible ? rootCombo.delegateModel : null
                currentIndex: rootCombo.highlightedIndex

                ScrollIndicator.vertical: ScrollIndicator { }
            }

            background: Rectangle {
                color: "#111417"
                border.color: "#1e2329"
                border.width: 1
                radius: 4
            }
        }
    }

    // Styled Checkbox
    component StyledCheckBox: CheckBox {
        id: rootCheck
        font.pixelSize: 12

        contentItem: Text {
            text: rootCheck.text
            font: rootCheck.font
            color: "#c8cdd4"
            leftPadding: rootCheck.indicator.width + rootCheck.spacing
            verticalAlignment: Text.AlignVCenter
        }

        indicator: Rectangle {
            implicitWidth: 18
            implicitHeight: 18
            x: rootCheck.leftPadding
            y: parent.height / 2 - height / 2
            radius: 3
            color: "#16191f"
            border.color: rootCheck.checked ? "#00e676" : "#1e2329"
            border.width: 1

            Rectangle {
                width: 10
                height: 10
                x: 4
                y: 4
                radius: 2
                color: "#00e676"
                visible: rootCheck.checked
            }
        }
    }

    // Styled Action/Normal Button
    component StyledButton: Button {
        id: rootBtn
        property color customBgColor: "#16191f"
        property color customTextColor: "#c8cdd4"
        property color customBorderColor: "#1e2329"

        font.pixelSize: 11
        font.bold: true

        contentItem: Text {
            text: rootBtn.text
            font: rootBtn.font
            color: rootBtn.customTextColor
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        background: Rectangle {
            id: bgRect
            color: rootBtn.pressed ? Qt.darker(rootBtn.customBgColor, 1.2) : 
                   rootBtn.hovered ? Qt.lighter(rootBtn.customBgColor, 1.2) : rootBtn.customBgColor
            border.color: rootBtn.activeFocus ? "#00e676" : rootBtn.customBorderColor
            border.width: 1
            radius: 4

            // Clean smooth scaling click animation
            scale: rootBtn.pressed ? 0.97 : 1.0
            Behavior on scale { NumberAnimation { duration: 80 } }
            Behavior on color { ColorAnimation { duration: 120 } }
        }
    }
}
