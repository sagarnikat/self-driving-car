const ModelManager = (() => {
    const STORAGE_KEY = "savedModels";

    function getModels(){
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
        } catch(e){
            return [];
        }
    }

    function setModels(models){
        localStorage.setItem(STORAGE_KEY, JSON.stringify(models));
    }

    function saveModel(name, brain, fitness){
        const models = getModels();
        const data = brain.toJSON ? brain.toJSON() : brain;
        const existing = models.findIndex(m => m.name === name);
        const entry = {
            name: name,
            architecture: data.architecture,
            brain: data,
            fitness: fitness != null ? Math.round(fitness) : 0,
            savedAt: new Date().toISOString()
        };
        if(existing >= 0){
            models[existing] = entry;
        } else {
            models.push(entry);
        }
        setModels(models);
        return entry;
    }

    function loadModel(name){
        const models = getModels();
        const entry = models.find(m => m.name === name);
        if(!entry) return null;
        return NeuralNetwork.fromJSON(entry.brain);
    }

    function deleteModel(name){
        const models = getModels().filter(m => m.name !== name);
        setModels(models);
    }

    function getModelInfo(name){
        return getModels().find(m => m.name === name) || null;
    }

    function listModels(){
        return getModels().map(m => ({
            name: m.name,
            architecture: m.architecture,
            fitness: m.fitness,
            savedAt: m.savedAt
        }));
    }

    function exportModel(name){
        const models = getModels();
        const entry = models.find(m => m.name === name);
        if(!entry) return;
        const blob = new Blob([JSON.stringify(entry, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = name + ".json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    function importModel(file){
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const entry = JSON.parse(e.target.result);
                    if(!entry.name || !entry.brain || !entry.brain.architecture){
                        reject(new Error("Invalid model file"));
                        return;
                    }
                    const models = getModels();
                    const existing = models.findIndex(m => m.name === entry.name);
                    if(existing >= 0){
                        models[existing] = entry;
                    } else {
                        models.push(entry);
                    }
                    setModels(models);
                    resolve(entry);
                } catch(err){
                    reject(err);
                }
            };
            reader.readAsText(file);
        });
    }

    return { saveModel, loadModel, deleteModel, getModelInfo, listModels, exportModel, importModel };
})();
