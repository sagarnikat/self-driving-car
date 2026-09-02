class Sensor{
    constructor(car){
        this.car = car;
        this.raycount = 3;
        this.rayLength = 100;
        this.raySpread = Math.PI/4;

        this.rays=[];
        this.readings=[];
    }

    update(roadBoarders){
        this.#castRays();
        this.readings=[];
        for(let i =0;i<this.rays.length;i++){
            this.readings.push(
                this.#getReading(this.rays[i],roadBoarders)
            )
        }
    }

    #getReading(ray,roadBoarders){
        
    }

    #castRays(){
        this.rays = [];
        for(let i =0;i<this.raycount;i++){
            const rayAngle=lerp(
                this.raySpread/2,
                -this.raySpread/2,
                this.raycount==1?0.5:i/(this.raycount-1)
            )+this.car.angle;

            const start = {x:this.car.x,y:this.car.y};
            const end = {
                x:this.car.x-Math.sin(rayAngle)*this.rayLength,
                y:this.car.y-Math.cos(rayAngle)*this.rayLength
            };
            this.rays.push([start,end]);
        }
    }

    draw(ctx){
        for(let i =0;i<this.raycount;i++){
            ctx.beginPath();
            ctx.lineWidth = 2;
            ctx.strokeStyle="yellow";
            ctx.moveTo(
                this.rays[i][0].x,
                this.rays[i][0].y
            );
            ctx.lineTo(
                this.rays[i][1].x,
                this.rays[i][1].y
            );
            ctx.stroke();
        }
    }

}