// npx tsx test_busy.ts
import axios from "axios";

const payload_test = {
    workers: [
        { id: 101, types: ["A"] },
        { id: 102, types: ["C"] },
        { id: 103, types: ["E", "H"], busy_windows: [[20, 60]] },
        { id: 104, types: ["G"] },
        { id: 105, types: ["B"] },
        { id: 106, types: ["D", "F"] },
    ],
    machines: [
        { id: 201, types: ["A"] },
        {
            id: 202,
            types: ["C", "F", "H", "D"],
            busy_windows: [[0, 5], [10, 15], [30, 50]],
        },
        { id: 203, types: ["E"] },
        { id: 204, types: ["G"] },
        { id: 205, types: ["B"] },
    ],
    tasks: [
        { id: 1, type: "A", duration: 4, earliest_start: 0, deadline: 100 },
        { id: 2, type: "B", duration: 3, earliest_start: 0, deadline: 100 },
        { id: 3, type: "C", duration: 5, earliest_start: 0, deadline: 100 },
        { id: 4, type: "D", duration: 2, earliest_start: 0, deadline: 100 },
        { id: 5, type: "E", duration: 6, earliest_start: 0, deadline: 100 },
        { id: 6, type: "F", duration: 3, earliest_start: 0, deadline: 10 },
        { id: 7, type: "G", duration: 4, earliest_start: 0, deadline: 100 },
        { id: 8, type: "H", duration: 2, earliest_start: 0, deadline: 100 },
        { id: 9, type: "A", duration: 5, earliest_start: 0, deadline: 100 },
        { id: 10, type: "B", duration: 1, earliest_start: 0, deadline: 100 },
        { id: 11, type: "C", duration: 4, earliest_start: 0, deadline: 30 },
        { id: 12, type: "D", duration: 3, earliest_start: 0, deadline: 100 },
        { id: 13, type: "E", duration: 2, earliest_start: 0, deadline: 100 },
        { id: 14, type: "F", duration: 6, earliest_start: 0, deadline: 25 },
        { id: 15, type: "G", duration: 3, earliest_start: 0, deadline: 100 },
        { id: 16, type: "H", duration: 4, earliest_start: 0, deadline: 100 },
    ],
};

async function main() {
    try {
        const res = await axios.post(
            "http://127.0.0.1:8000/schedule_with_busy",
            payload_test,
            { headers: { "Content-Type": "application/json" } }
        );
        console.log(JSON.stringify(res.data, null, 2));
    } catch (err: any) {
        console.error("Request failed:", err.response?.data || err.message);
    }
}

main();
