function createSettingsPanel(onApply, onReset) {
    const btn = document.createElement("button");
    btn.id = "settingsBtn";
    btn.textContent = "⚙";
    btn.title = "Settings";
    document.body.appendChild(btn);

    const overlay = document.createElement("div");
    overlay.id = "settingsOverlay";
    overlay.style.display = "none";

    const panel = document.createElement("div");
    panel.id = "settingsPanel";

    const title = document.createElement("h3");
    title.textContent = "Car Settings";
    panel.appendChild(title);

    const fields = [
        { key: "acceleration", label: "Acceleration", type: "number", step: "0.1", min: "0" },
        { key: "maxSpeed", label: "Max Speed", type: "number", step: "0.5", min: "0" },
        { key: "friction", label: "Friction", type: "number", step: "0.01", min: "0" },
        { key: "canRotate", label: "Can Rotate", type: "checkbox" },
        { key: "turnAngle", label: "Turn Angle", type: "number", step: "0.01", min: "0" },
        { key: "lateralSpeed", label: "Lateral Speed", type: "number", step: "0.5", min: "0" },
        { key: "startLane", label: "Start Lane", type: "number", step: "1", min: "0" },
        // { key: "startY", label: "Start Y", type: "number", step: "10", min: "0" }
    ];

    const inputs = {};
    for (const f of fields) {
        const row = document.createElement("div");
        row.className = "settingsRow";
        const label = document.createElement("label");
        label.textContent = f.label;
        label.htmlFor = "car_" + f.key;
        const input = document.createElement("input");
        input.id = "car_" + f.key;
        input.type = f.type;
        if (f.type === "checkbox") {
            input.checked = !!CONFIG.car[f.key];
        } else {
            input.type = "number";
            input.step = f.step;
            input.min = f.min;
            input.value = CONFIG.car[f.key];
        }
        inputs[f.key] = input;
        row.appendChild(label);
        row.appendChild(input);
        panel.appendChild(row);
    }

    const applyBtn = document.createElement("button");
    applyBtn.textContent = "Apply";
    applyBtn.addEventListener("click", () => {
        for (const f of fields) {
            const input = inputs[f.key];
            if (f.type === "checkbox") {
                CONFIG.car[f.key] = input.checked;
            } else {
                CONFIG.car[f.key] = parseFloat(input.value);
            }
        }
        if (onApply) onApply();
        overlay.style.display = "none";
    });

    const resetBtn = document.createElement("button");
    resetBtn.textContent = "Reset";
    resetBtn.addEventListener("click", () => {
        if (onReset) onReset();
        overlay.style.display = "none";
    });

    const closeBtn = document.createElement("button");
    closeBtn.textContent = "Close";
    closeBtn.addEventListener("click", () => {
        overlay.style.display = "none";
    });

    const btnRow = document.createElement("div");
    btnRow.className = "settingsBtns";
    btnRow.appendChild(applyBtn);
    btnRow.appendChild(resetBtn);
    btnRow.appendChild(closeBtn);
    panel.appendChild(btnRow);

    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    btn.addEventListener("click", () => {
        for (const f of fields) {
            const input = inputs[f.key];
            if (f.type === "checkbox") {
                input.checked = !!CONFIG.car[f.key];
            } else {
                input.value = CONFIG.car[f.key];
            }
        }
        overlay.style.display = "flex";
    });

    return { button: btn, overlay, inputs };
}
