function createModelManagerUI(onLoadModel, onSaveModel) {
    const btn = document.createElement("button");
    btn.id = "modelManagerBtn";
    btn.textContent = "🧠";
    btn.title = "Model Manager";
    document.body.appendChild(btn);

    const overlay = document.createElement("div");
    overlay.id = "modelManagerOverlay";
    overlay.style.display = "none";

    const panel = document.createElement("div");
    panel.id = "modelManagerPanel";

    const title = document.createElement("h3");
    title.textContent = "Model Manager";
    panel.appendChild(title);

    const saveRow = document.createElement("div");
    saveRow.className = "mm-saveRow";

    const nameInput = document.createElement("input");
    nameInput.id = "mmNameInput";
    nameInput.type = "text";
    nameInput.placeholder = "Model name";

    const saveBtn = document.createElement("button");
    saveBtn.id = "mmSaveBtn";
    saveBtn.textContent = "💾 Save Current";
    saveBtn.title = "Save the currently best performing model";

    saveRow.appendChild(nameInput);
    saveRow.appendChild(saveBtn);
    panel.appendChild(saveRow);

    const importLabel = document.createElement("label");
    importLabel.id = "mmImportLabel";
    importLabel.textContent = "⬆️ Import";
    const importInput = document.createElement("input");
    importInput.id = "mmImportInput";
    importInput.type = "file";
    importInput.accept = ".json,application/json";
    importInput.style.display = "none";
    importLabel.appendChild(importInput);
    panel.appendChild(importLabel);

    const list = document.createElement("div");
    list.id = "mmModelList";
    panel.appendChild(list);

    const listTitle = document.createElement("div");
    listTitle.className = "mmListTitle";
    listTitle.textContent = "Saved Models";
    panel.appendChild(listTitle);
    panel.insertBefore(listTitle, list);

    const refreshList = () => {
        list.innerHTML = "";
        const models = ModelManager.listModels();
        if (models.length === 0) {
            const empty = document.createElement("div");
            empty.className = "mmEmpty";
            empty.textContent = "No saved models yet";
            list.appendChild(empty);
            return;
        }
        models.forEach((model) => {
            const row = document.createElement("div");
            row.className = "mmRow";

            const info = document.createElement("div");
            info.className = "mmInfo";

            const name = document.createElement("div");
            name.className = "mmName";
            name.textContent = model.name;

            const meta = document.createElement("div");
            meta.className = "mmMeta";
            meta.textContent =
                `${model.architecture.join("→")} · ` +
                (model.generation != null ? `Gen ${model.generation} · ` : "") +
                `Score ${model.fitness} · ` +
                new Date(model.savedAt).toLocaleString();
            info.appendChild(name);
            info.appendChild(meta);
            row.appendChild(info);

            const loadBtn = document.createElement("button");
            loadBtn.textContent = "Load";
            loadBtn.className = "mmLoadBtn";
            loadBtn.addEventListener("click", () => {
                const brain = ModelManager.loadModel(model.name);
                if (brain && onLoadModel) onLoadModel(brain, model.name);
                overlay.style.display = "none";
            });
            row.appendChild(loadBtn);

            const exportBtn = document.createElement("button");
            exportBtn.textContent = "Export";
            exportBtn.className = "mmExportBtn";
            exportBtn.addEventListener("click", () => {
                ModelManager.exportModel(model.name);
            });
            row.appendChild(exportBtn);

            const delBtn = document.createElement("button");
            delBtn.textContent = "Delete";
            delBtn.className = "mmDeleteBtn";
            delBtn.addEventListener("click", () => {
                ModelManager.deleteModel(model.name);
                refreshList();
            });
            row.appendChild(delBtn);

            list.appendChild(row);
        });
    };

    saveBtn.addEventListener("click", () => {
        let name = nameInput.value.trim();
        if (!name) {
            name = "model_" + new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
            nameInput.value = name;
        }
        if (onSaveModel) onSaveModel(name);
        refreshList();
    });

    importInput.addEventListener("change", async () => {
        const file = importInput.files[0];
        if (!file) return;
        try {
            await ModelManager.importModel(file);
            refreshList();
            alert("Model imported!");
        } catch (e) {
            alert("Failed to import: " + e.message);
        }
        importInput.value = "";
    });

    const closeBtn = document.createElement("button");
    closeBtn.textContent = "Close";
    closeBtn.className = "mmCloseBtn";
    closeBtn.addEventListener("click", () => {
        overlay.style.display = "none";
    });

    const btnRow = document.createElement("div");
    btnRow.className = "settingsBtns";
    btnRow.appendChild(closeBtn);
    panel.appendChild(btnRow);

    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    btn.addEventListener("click", () => {
        refreshList();
        overlay.style.display = "flex";
    });

    return { button: btn, overlay, refreshList };
}