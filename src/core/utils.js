function lerp(a,b,t){
    return a+(b-a)*t;
}

function getIntersection(A, B, C, D) {
    const tTop = (D.x - C.x) * (A.y - C.y) - (D.y - C.y) * (A.x - C.x);
    const uTop = (C.y - A.y) * (A.x - B.x) - (C.x - A.x) * (A.y - B.y);
    const bottom = (D.y - C.y) * (B.x - A.x) - (D.x - C.x) * (B.y - A.y);

    if (bottom != 0) {
        const t = tTop / bottom;
        const u = uTop / bottom;

        if (t >= 0 && t <= 1 && u >= 0 && u <= 1) {
            return {
                x: lerp(A.x, B.x, t),
                y: lerp(A.y, B.y, t),
                offset: t
            };
        }
    }

    return null;
}

function getRGBA(value){
    const alpha = Math.abs(value);
    const R = value < 0 ? 0 : 255;
    const G = R;
    const B = value > 0 ? 0 : 255;
    return "rgba("+R+","+G+","+B+","+alpha+")";
}

function downloadBrain(network, filename = "network.txt"){
    const lines = [];
    lines.push("NEURAL NETWORK");
    lines.push("==============");
    lines.push("");

    network.levels.forEach((level, li) => {
        lines.push("LEVEL " + li);
        lines.push("  Inputs:  " + level.inputs.length);
        lines.push("  Outputs: " + level.outputs.length);
        lines.push("");
        lines.push("  Biases:");
        level.biases.forEach((b) => lines.push("    " + b.toFixed(4)));
        lines.push("");
        lines.push("  Weights (row=input, col=output):");
        for(let i = 0; i < level.weights.length; i++){
            const row = level.weights[i]
                .map((w) => w.toFixed(4))
                .join("  ");
            lines.push("    [" + row + "]");
        }
        lines.push("");
    });

    const text = lines.join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function polysIntersect(poly1,poly2){
    for(let i =0;i<poly1.length;i++){
        for(let j =0;j<poly2.length;j++){
            const touch = getIntersection(
                poly1[i],
                poly1[(i+1)%poly1.length],
                poly2[j],
                poly2[(j+1)%poly2.length],
            );
            if(touch)
                return true;
        }
    }

    return false;
}
