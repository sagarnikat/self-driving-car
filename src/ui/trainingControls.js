function createTrainingControls(onStart, onPause, onStop, onConfigChange, getState) {
    const btn = document.createElement("button");
    btn.id = "trainingBtn";
    btn.textContent = "🏁";
    btn.title = "Training Controls";
    document.body.appendChild(btn);

    const overlay = document.createElement("div");
    overlay.id = "trainingOverlay";
    overlay.style.display = "none";

    const panel = document.createElement("div");
    panel.id = "trainingPanel";

    const title = document.createElement("h3");
    title.textContent = "Training Controls";
    panel.appendChild(title);

    const stateLine = document.createElement("div");
    stateLine.id = "trainingState";
    stateLine.className = "trainingState";
    panel.appendChild(stateLine);

    const btnRow = document.createElement("div");
    btnRow.className = "trainingBtns";

    const startBtn = document.createElement("button");
    startBtn.textContent = "Start";
    startBtn.className = "trainingStartBtn";

    const pauseBtn = document.createElement("button");
    pauseBtn.textContent = "Pause";
    pauseBtn.className = "trainingPauseBtn";

    const stopBtn = document.createElement("button");
    stopBtn.textContent = "Stop";
    stopBtn.className = "trainingStopBtn";

    btnRow.appendChild(startBtn);
    btnRow.appendChild(pauseBtn);
    btnRow.appendChild(stopBtn);
    panel.appendChild(btnRow);

    const inputRow = (labelText, initVal, opts) => {
        const r = document.createElement("div");
        r.className = "trainingInputRow";
        const label = document.createElement("label");
        label.textContent = labelText;
        const input = document.createElement("input");
        input.type = "number";
        input.value = initVal;
        if (opts) {
            if (opts.min !== undefined) input.min = opts.min;
            if (opts.max !== undefined) input.max = opts.max;
            if (opts.step !== undefined) input.step = opts.step;
        }
        r.appendChild(label);
        r.appendChild(input);
        return { row: r, input };
    };

    const genRow = inputRow("Generations", 0, { min: 0, step: 1 });
    genRow.input.title = "0 = run forever; otherwise stop after this many generations";

    const popRow = inputRow("Population", String(currentCarConfig.count), { min: 1, max: 500, step: 1 });

    const mutRow = inputRow("Mutation rate", String(CONFIG.evolution.mutationRate), { min: 0, max: 1, step: 0.01 });

    panel.appendChild(genRow.row);
    panel.appendChild(popRow.row);
    panel.appendChild(mutRow.row);

    const refresh = () => {
        const info = getState();
        const state = info.state;
        stateLine.textContent = state;
        stateLine.className = "trainingState " + state.toLowerCase();
        startBtn.textContent = state === "running" ? "Running" : state === "paused" ? "Resume" : "Start";
        startBtn.disabled = state === "running";
        pauseBtn.disabled = state !== "running";
        stopBtn.disabled = state === "stopped";
        if (info.generations != null) genRow.input.value = info.generations;
        if (info.population != null) popRow.input.value = info.population;
        if (info.mutationRate != null) mutRow.input.value = info.mutationRate;
    };

    genRow.input.addEventListener("change", () => {
        const val = Math.max(0, parseInt(genRow.input.value, 10) || 0);
        genRow.input.value = val;
        onConfigChange({ generations: val });
    });

    popRow.input.addEventListener("change", () => {
        const val = Math.max(1, Math.min(500, parseInt(popRow.input.value, 10) || CONFIG.sim.defaultCarCount));
        popRow.input.value = val;
        onConfigChange({ population: val });
    });

    mutRow.input.addEventListener("change", () => {
        const val = Math.max(0, Math.min(1, parseFloat(mutRow.input.value)));
        mutRow.input.value = val;
        onConfigChange({ mutationRate: val });
    });

    startBtn.addEventListener("click", () => onStart());
    pauseBtn.addEventListener("click", () => onPause());
    stopBtn.addEventListener("click", () => onStop());

    btn.addEventListener("click", () => {
        refresh();
        overlay.style.display = "flex";
    });

    const closeBtn = document.createElement("button");
    closeBtn.textContent = "Close";
    closeBtn.className = "trainingCloseBtn";
    closeBtn.addEventListener("click", () => {
        overlay.style.display = "none";
    });
    panel.appendChild(closeBtn);

    overlay.appendChild(panel);
    document.body.appendChild(overlay);
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) overlay.style.display = "none";
    });

    return { refresh, overlay };
}