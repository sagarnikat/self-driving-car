class Fitness {
    constructor(car, traffic) {
        this.car = car;
        this.traffic = traffic;
        this.startTime = Date.now();
        this.deathTime = null;
        this.carsPassed = 0;
        this.counted = new Set();
        this.lastY = car.y;
    }

    update() {
        if (this.deathTime === null && this.car.damaged) {
            this.deathTime = Date.now();
        }
        if (this.car.damaged) return;

        const currentY = this.car.y;

        for (let i = 0; i < this.traffic.length; i++) {
            const t = this.traffic[i];
            if (this.counted.has(t)) continue;
            if (this.lastY > t.y && currentY <= t.y) {
                this.carsPassed++;
                this.counted.add(t);
            }
        }

        this.lastY = currentY;
    }

    getDistance() {
        const dist = 100 - this.car.y;
        if (dist < 0) return 0;
        return dist;
    }

    getTimeAlive() {
        const end = this.deathTime !== null ? this.deathTime : Date.now();
        return (end - this.startTime) / 1000;
    }

    calculateScore() {
        const distance = this.getDistance();
        const passedBonus = this.carsPassed * CONFIG.fitness.passedBonus;

        if (this.car.damaged) {
            return distance + passedBonus;
        }

        const timeAlive = this.getTimeAlive();
        return distance + passedBonus + (timeAlive * CONFIG.fitness.timeAliveMultiplier);
    }
}
