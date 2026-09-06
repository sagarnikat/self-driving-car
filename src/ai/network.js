class NeuralNetwork{
    constructor(neuronCounts){
        this.levels=[];
        this.architecture = [...neuronCounts];
        for(let i =0;i<neuronCounts.length-1;i++){
            this.levels.push(new Level(
                neuronCounts[i],neuronCounts[i+1]
            ));
        }
    }

    toJSON(){
        return {
            architecture: this.architecture,
            levels: this.levels.map(level => ({
                inputCount: level.inputs.length,
                outputCount: level.outputs.length,
                biases: [...level.biases],
                weights: level.weights.map(row => [...row])
            }))
        };
    }

    static fromJSON(data){
        const architecture = data.architecture || data.levels.map(l => l.inputs ? l.inputs.length : 0).concat(
            data.levels.length ? data.levels[data.levels.length - 1].outputs.length : 0
        );
        const nn = new NeuralNetwork(architecture);
        for(let i = 0; i < data.levels.length; i++){
            nn.levels[i].biases = [...data.levels[i].biases];
            for(let j = 0; j < data.levels[i].weights.length; j++){
                nn.levels[i].weights[j] = [...data.levels[i].weights[j]];
            }
        }
        return nn;
    }

    static feedForward(givenInpts,network){
        let outputs = Level.feedForward(
            givenInpts,network.levels[0])
        for(let i =1;i<network.levels.length;i++){
            outputs = Level.feedForward(
                outputs,network.levels[i]);
        }

        return outputs;
    }

    static mutate(network,amount = CONFIG.network.mutationAmount){
        network.levels.forEach(level => {
            for(let i = 0;i<level.biases.length;i++){
                level.biases[i]=lerp(
                    level.biases[i],
                    Math.random()*2-1,
                    amount
                )
            }
            for(let i=0;i<level.weights.length;i++){
                for(let j =0;j<level.weights[i].length;j++){
                    level.weights[i][j]=lerp(
                        level.weights[i][j],
                        Math.random()*2-1,
                        amount
                    )
                }
            }
        });
    }
}



class Level{
    constructor(inputCount,outputCount){
        this.inputs = new Array(inputCount);
        this.outputs = new Array(outputCount);
        this.biases = new Array(outputCount);

        this.weights =[];
        for(let i =0;i<inputCount;i++){
            this.weights[i]= new Array(outputCount);
        }

        Level.#randomize(this);
    }

    static #randomize(level){
        for(let i=0;i<level.inputs.length;i++){
            for(let j=0;j<level.outputs.length;j++){
                level.weights[i][j]=Math.random()*2-1;
            }
        }

        for(let i =0;i<level.biases.length;i++){
            level.biases[i] = Math.random()*2 -1;
        }
    }

    static feedForward(givenInpts,level){
        for(let i =0;i<level.inputs.length;i++){
            level.inputs[i] = givenInpts[i];
        }

        for(let i =0;i<level.outputs.length;i++){
            let sum = 0;
            for(let j =0;j <level.inputs.length;j++){
                sum+=level.inputs[j]*level.weights[j][i];
            }

            if(sum>level.biases[i]){
                level.outputs[i] = 1;
            }else{
                level.outputs[i] = 0;
            }
        }

        return level.outputs;
    }
}
