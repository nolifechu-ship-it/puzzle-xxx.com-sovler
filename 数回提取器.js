(function() {
    // 1. 抓取所有数回数字格
    let cells = Array.from(document.querySelectorAll('.loop-task-cell'));
    if (!cells.length) {
        console.error("未找到 .loop-task-cell 元素，请确认处于游戏主界面！");
        return;
    }

    // 2. 按照物理像素坐标聚类成行 (5px 容差防抖动)
    cells.sort((a, b) => a.offsetTop - b.offsetTop || a.offsetLeft - b.offsetLeft);

    let rowsMap = new Map();
    cells.forEach(c => {
        let top = c.offsetTop;
        let foundKey = null;
        for (let k of rowsMap.keys()) {
            if (Math.abs(k - top) < 5) {
                foundKey = k;
                break;
            }
        }
        if (foundKey === null) {
            foundKey = top;
            rowsMap.set(foundKey, []);
        }
        rowsMap.get(foundKey).push(c);
    });

    let sortedRowTops = Array.from(rowsMap.keys()).sort((a, b) => a - b);
    let height = sortedRowTops.length;
    let width = rowsMap.get(sortedRowTops[0]).length;

    // 3. 构建长方形二维矩阵 (0~3 存为整数，空格存为 None)
    let target = [];
    for (let topKey of sortedRowTops) {
        let rowCells = rowsMap.get(topKey);
        rowCells.sort((a, b) => a.offsetLeft - b.offsetLeft);

        let rowData = [];
        for (let c of rowCells) {
            let txt = c.innerText.trim();
            rowData.push(txt !== "" && !isNaN(txt) ? parseInt(txt) : null);
        }
        target.push(rowData);
    }

    // 4. 组装 Python 代码并复制到剪贴板
    let pyCode = `width = ${width}\n` +
                 `height = ${height}\n` +
                 `target = ${JSON.stringify(target).replace(/null/g, "None")}`;

    copy(pyCode);

    console.log(`%c✔ 数回数据抓取成功！尺寸: 宽 ${width} x 高 ${height}`, "color: green; font-size: 14px; font-weight: bold;");
    console.log("前两行预览:", target.slice(0, 2));
    console.log("已复制到剪贴板，直接在 Python 里 Ctrl+V！");
})();