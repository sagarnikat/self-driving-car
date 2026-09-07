const BenchmarkStore = (() => {
    const STORAGE_KEY = "benchmarkScores";
    const FILE_NAME = "benchmark_scores.csv";
    const HEADER = "generation,averageScore,bestScore,bestDistance,bestCarsPassed,bestTimeAlive";

    function normalize(entry) {
        if (entry.averageScore === undefined) {
            return {
                generation: entry.generation,
                averageScore: entry.score,
                bestScore: entry.score,
                bestDistance: entry.distance,
                bestCarsPassed: entry.carsPassed,
                bestTimeAlive: entry.timeAlive
            };
        }
        return entry;
    }

    function load() {
        try {
            return (JSON.parse(localStorage.getItem(STORAGE_KEY)) || []).map(normalize);
        } catch (e) {
            return [];
        }
    }

    function persist(entries) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    }

    function getEntries() {
        return load();
    }

    function addEntry(entry) {
        const entries = load();
        entries.push(entry);
        persist(entries);
        return entry;
    }

    function clear() {
        persist([]);
    }

    function rowToCSV(entry) {
        return [
            entry.generation,
            entry.averageScore,
            entry.bestScore,
            entry.bestDistance,
            entry.bestCarsPassed,
            entry.bestTimeAlive
        ].join(",");
    }

    function toCSV(entries) {
        return [HEADER, ...entries.map(rowToCSV)].join("\n") + "\n";
    }

    function downloadCSV() {
        const entries = load();
        const blob = new Blob([toCSV(entries)], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = FILE_NAME;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    return { getEntries, addEntry, clear, toCSV, downloadCSV };
})();