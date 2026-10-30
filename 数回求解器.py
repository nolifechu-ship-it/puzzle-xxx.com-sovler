from playwright.sync_api import sync_playwright
import tkinter as tk
import colorsys
from itertools import product

class SamexButDiffbError(Exception):
    pass

class CloseError(Exception):
    pass

class UnknownError(Exception):
    pass

def fetch_loop(url="https://www.puzzle-loop.com/"):
    """
    输入数回网页链接（支持每日、特殊长方形等任意页面），
    后台静默抓取并直接返回 (width, height, target)
    - width: 宽（列数）
    - height: 高（行数）
    - target: 2D 矩阵，数字为 0~3，空格为 None
    """
    print(f"正在后台启动无头浏览器抓取数回页面: {url} ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        # 核心等待：等棋盘所有数字单元格加载就位
        page.wait_for_selector(".board-back .loop-task-cell")

        data = page.evaluate("""() => {
            let cells = Array.from(document.querySelectorAll('.loop-task-cell'));

            // 5px 像素聚类
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

            return { width: width, height: height, target: target };
        }""")

        browser.close()
        print(f"✔ 抓取成功！识别尺寸: 宽 {data['width']} x 高 {data['height']}")
        return data["width"], data["height"], data["target"]

def show_slitherlink(width, height, target, grid):
    """
    数回若尔当对偶双极染色可视化 (x.0 / x.5 精准无浮点误差版)
    :param width: 棋盘宽度（列数）
    :param height: 棋盘高度（行数）
    :param target: 2D 矩阵 (数字 0~3，空格为 None)
    :param grid: 2D 矩阵 (-1 为未知, 0.0/0.5 绝对内外, x.0/x.5 相对簇)
    """
    root = tk.Tk()
    root.title(f"Slitherlink Dual-Coloring - {width}x{height}")

    # 自适应计算单元格大小
    cell_size = max(22, min(42, 800 // max(width, height)))
    margin_x = 45
    margin_y = 45

    canvas_w = margin_x * 2 + cell_size * width
    canvas_h = margin_y * 2 + cell_size * height

    canvas = tk.Canvas(root, width=canvas_w, height=canvas_h, bg="#FFFFFF")
    canvas.pack(padx=10, pady=10)

    # 动态色盘生成器 (支持任意不连续的非负整数 x)
    def get_color_scheme(comp_id):
        if comp_id == 0:
            # 官网原版绝对内外预设
            # 0.5 绝对内 (淡紫) | 0.0 绝对外 (粉红网纹)
            return "#C8C8FC", "#E57373", "#FFF2F2"
        
        # 黄金分割率步进生成无限种高对比度柔和颜色
        golden_ratio = 0.618033988749895
        h = (comp_id * golden_ratio) % 1.0
        
        # 实心纯色 (x.5)
        r1, g1, b1 = colorsys.hsv_to_rgb(h, 0.38, 0.98)
        solid_hex = f"#{int(r1*255):02x}{int(g1*255):02x}{int(b1*255):02x}"
        
        # 网纹线条色 (x.0)
        r2, g2, b2 = colorsys.hsv_to_rgb(h, 0.70, 0.75)
        hatch_line_hex = f"#{int(r2*255):02x}{int(g2*255):02x}{int(b2*255):02x}"
        
        # 网纹微底色
        r3, g3, b3 = colorsys.hsv_to_rgb(h, 0.12, 0.99)
        hatch_bg_hex = f"#{int(r3*255):02x}{int(g3*255):02x}{int(b3*255):02x}"
        
        return solid_hex, hatch_line_hex, hatch_bg_hex

    # 严格锁死在格子边界内、绝不穿模的 45度 菱形交叉网纹
    def draw_mesh(x1, y1, x2, y2, bg_col, line_col):
        canvas.create_rectangle(x1, y1, x2, y2, fill=bg_col, outline="#E0E0E0", width=1)
        S = cell_size
        step = max(7, S // 4)

        # 方向 1：左下到右上斜线 (u + v = D)
        for D in range(step, 2 * S, step):
            if D <= S:
                canvas.create_line(x1, y1 + D, x1 + D, y1, fill=line_col, width=1)
            else:
                m = D - S
                canvas.create_line(x1 + m, y2, x2, y1 + m, fill=line_col, width=1)

        # 方向 2：左上到右下斜线 (u - v = D)
        for D in range(-S + step, S, step):
            if D >= 0:
                canvas.create_line(x1 + D, y1, x2, y2 - D, fill=line_col, width=1)
            else:
                m = -D
                canvas.create_line(x1, y1 + m, x2 - m, y2, fill=line_col, width=1)

    # 1. 绘制格子背景 (染色 / 网状 / 留白)
    for r in range(height):
        for c in range(width):
            x1 = margin_x + c * cell_size
            y1 = margin_y + r * cell_size
            x2 = x1 + cell_size
            y2 = y1 + cell_size

            state = grid[r][c]

            if state is None or state < -0.1:
                # -1: 未知，纯白留空
                canvas.create_rectangle(x1, y1, x2, y2, fill="#FFFFFF", outline="#E0E0E0", width=1)
            else:
                # 核心改动：解析 x.0 与 x.5 (彻底杜绝浮点误差)
                comp_id = int(state)
                # 小数部分大于 0.25 判定为极性 1 (即 x.5)，否则为极性 0 (即 x.0)
                polarity = 1 if (state % 1 >= 0.25) else 0

                solid_col, hatch_line, hatch_bg = get_color_scheme(comp_id)

                if polarity == 1:
                    # x.5: 实心纯色填充
                    canvas.create_rectangle(x1, y1, x2, y2, fill=solid_col, outline="#E0E0E0", width=1)
                else:
                    # x.0: 同色调 45° 交叉网纹
                    draw_mesh(x1, y1, x2, y2, hatch_bg, hatch_line)

    # 2. 绘制格子中的数字
    font_digit = ("Arial", max(9, int(cell_size * 0.45)), "bold")
    for r in range(height):
        for c in range(width):
            clue = target[r][c]
            if clue is not None:
                cx = margin_x + c * cell_size + cell_size / 2
                cy = margin_y + r * cell_size + cell_size / 2
                canvas.create_text(cx, cy, text=str(clue), font=font_digit, fill="#000000")

    # 3. 绘制数回经典的晶格黑点 (Lattice Dots)
    dot_r = max(2, cell_size // 12)
    for r in range(height + 1):
        for c in range(width + 1):
            px = margin_x + c * cell_size
            py = margin_y + r * cell_size
            canvas.create_oval(px - dot_r, py - dot_r, px + dot_r, py + dot_r, fill="#000000", outline="#000000")

    # 4. 绘制坐标
    font_coord = ("Arial", max(8, int(cell_size * 0.3)), "normal")
    for c in range(width):
        cx = margin_x + c * cell_size + cell_size / 2
        letter = chr(ord('a') + c) if c < 26 else f"a{chr(ord('a') + c - 26)}"
        canvas.create_text(cx, margin_y - 18, text=letter, font=font_coord, fill="#999999")
    for r in range(height):
        cy = margin_y + r * cell_size + cell_size / 2
        canvas.create_text(margin_x - 18, cy, text=str(r + 1), font=font_coord, fill="#999999")

    root.mainloop()

def find_neig4(i,j):
    return [(i+1,j),(i-1,j),(i,j+1),(i,j-1)]

def find_neig8(i,j):#注意是斜角，不是8相邻
    return [(i+1,j+1),(i+1,j-1),(i-1,j+1),(i-1,j-1)]

def xor5(a,b):#5版本的异或，支持不同形式比较
    if str(float(a))==str(float(b)):
        return 0
    else:
        return 0.5

def xorint(a):#在x.0和x.5之间转换
    x = int(a)
    return x + 0.5 if a == x else float(x)

def find_foreparent(height,width,grid,alter):
    for i, j in product(range(height), range(width)):
        z=int(grid[i][j])
        b=grid[i][j]-z
        while z in alter:#找祖宗
            b=xor5(b,alter[z][1])
            z=alter[z][0]
        grid[i][j]=z+b

def main(width, height, target):
    #初始化：整体套一层-1
    #生成grid，额外有一个最外层，全为0
    grid=[[0]*(width+2) for _ in range(height+2)]
    #求解就是大一统的过程
    p=1
    for y, x in product(range(1,height+1), range(1,width+1)):
        grid[y][x]=p
        p+=1
    #对应的给target也加一层None
    target1=[[None]*(width+2)]
    for y in target:
        target1.append([None]+y+[None])
    target1.append([None]*(width+2))
    target=[[None]*(width+2) for _ in range(height+2)]
    for y, x in product(range(height+2), range(width+2)):
        target[y][x]=target1[y][x]
    #
    width+=2
    height+=2
    #创建一个转换表
    alter={}
    #初始化连通器，格式为[[[family,boundry]],[……]]
    liantong=[]
    temp=[]
    for y, x in product(range(height), range(width)):
        if grid[y][x]==0:
            temp.append((y,x))
        else:
            liantong.append([[(y,x)],find_neig4(y,x)])
    boundry=set()
    for i in temp:
        temp1=find_neig4(*i)
        for j in temp1:
            if j not in temp and 0<=j[0]<height and 0<=j[1]<width:
                boundry.add(j)

    liantong.append([temp,list(boundry)])


    def modify(y:int,x:int,z,b=None,grid=grid,alter=alter,height=height,width=width):#最伟大的功能
        if b is None:
            b=z-int(z)
            z=int(z)
        while z in alter:#找祖宗
            b=xor5(b,alter[z][1])
            z=alter[z][0]
        #顺便给现在的格子找祖宗
        check0=int(grid[y][x])
        check1=grid[y][x]-check0
        while check0 in alter:#找祖宗
            check1=xor5(check1,alter[check0][1])
            check0=alter[check0][0]
        if check0==z and check1==b:#重复
            return 0
        if check0==z and check1!=b:#出错！
            print(f'{y}行{x}列{z}区冲突！本来是{check0+check1}，现在是{z+b}')
            show_slitherlink(width, height, target, grid)
            raise SamexButDiffbError("出错！")
        if check0!=z:#合并！
            if z>check0:
                alter[z]=(check0,xor5(b,check1))
            else:
                alter[check0]=(z,xor5(b,check1))
            find_foreparent(height,width,grid,alter)#每次都运行，完美同步；这个最多触发面积次，性能问题不大
            return 1
        else:
            print('?')
            raise UnknownError('出错！')

    effect=1

    #游戏开始，这会是目前为止写过的最难求解器
    for y, x in product(range(height), range(width)):#先处理0,处理完就不存在0了
        if target[y][x]==0:
            z=grid[y][x]
            for lo in find_neig4(y,x):
                effect+=modify(lo[0],lo[1],z,0)
            target[y][x]=None

    
    while effect>0:
        effect=0
        #主循环
        #单数字考虑，这里采用策略而非穷举写法
        for y, x in product(range(height), range(width)):
            match target[y][x]:
                case None:
                    continue
                case 1:#周围四格有三个一样的
                    '''
                    策略：
                    与自己有关的：
                    1、周围有两个相同的，则自己被吸收√
                    2、自己和周围某个相反，则剩下三个直接确定√
                    与自己无关的：
                    3、周围有两个相同的，则剩下两个独立不同√
                    4、周围有两个不同的，则剩下两个独立相同√
                    '''
                    surround=find_neig4(y,x)
                    #统计周围的族
                    surroundlist=[grid[temp[0]][temp[1]] for temp in surround]
                    #先看有没有相同的
                    zuset=set()
                    chongfu=None
                    for temp in surroundlist:
                        if temp not in zuset:
                            zuset.add(temp)
                        else:
                            chongfu=temp
                    if chongfu is not None:#有重复！
                        #自己被吸收
                        effect+=modify(y,x,int(chongfu),chongfu-int(chongfu))
                        #另外两个被标为不同
                        difflist=[]
                        jihui=2
                        for temp in surround:
                            if grid[temp[0]][temp[1]]!=chongfu or jihui<=0:
                                difflist.append(temp)
                            else:
                                jihui-=1
                        if len(difflist)==2:
                            effect+=modify(difflist[0][0],difflist[0][1],xorint(grid[difflist[1][0]][difflist[1][1]]))

                    #看看有没有自己和周围相反
                    for temp in surroundlist:
                        if int(grid[y][x])==int(temp) and grid[y][x]!=temp:#相反
                            for temp in surround:#进入下阶段，不是相反的全部同化
                                if int(grid[temp[0]][temp[1]])!=int(grid[y][x]):
                                    effect+=modify(temp[0],temp[1],grid[y][x])
                            break
                    #看看周围有没有两个不同
                    for temp1,temp2 in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3)):
                        if int(surroundlist[temp1])==int(surroundlist[temp2]) and surroundlist[temp1]!=surroundlist[temp2]:#不同！
                            difflist=[temp for temp in range(4) if (temp!=temp1 and temp!=temp2)]
                            if len(difflist)==2:
                                temp1,temp2=surround[difflist[0]],surround[difflist[1]]
                                effect+=modify(temp1[0],temp1[1],grid[temp2[0]][temp2[1]])
                            else:
                                raise UnknownError('4-2≠2')
                            break
                    #如果四周已统一，就没用了
                    surround=find_neig4(y,x)
                    surroundlist=set([int(grid[temp[0]][temp[1]]) for temp in surround+[(y,x)]])
                    if len(surroundlist)==1:
                        target[y][x]=None
                    
                case 2:#周围四格两两一组
                    '''
                    策略（完全与自己无关）：
                    1、周围有两个相同的，则剩下两个与这俩相反√
                    2、周围有两个不同的，则剩下两个独立不同√
                    '''
                    surround=find_neig4(y,x)
                    #统计周围的族
                    surroundlist=[grid[temp[0]][temp[1]] for temp in surround]
                    #先看有没有相同的
                    zuset=set()
                    chongfu=None#这里重复指族
                    for temp in surroundlist:
                        if temp not in zuset:
                            zuset.add(temp)
                        else:
                            chongfu=temp
                    if chongfu is not None:#有重复！
                        #随便找一个重复
                        for temp in surround:
                            if grid[temp[0]][temp[1]]==chongfu:
                                chongfu=temp#注意这里重复变成了坐标
                                break
                        #另外两个被相反
                        for temp in surround:
                            if grid[temp[0]][temp[1]]!=grid[chongfu[0]][chongfu[1]]:
                                effect+=modify(temp[0],temp[1],xorint(grid[chongfu[0]][chongfu[1]]))

                    #再看有没有相反的
                    for temp1,temp2 in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3)):
                        if int(surroundlist[temp1])==int(surroundlist[temp2]) and surroundlist[temp1]!=surroundlist[temp2]:#不同！
                            difflist=[temp for temp in range(4) if (temp!=temp1 and temp!=temp2)]
                            if len(difflist)==2:
                                temp1,temp2=surround[difflist[0]],surround[difflist[1]]
                                effect+=modify(temp1[0],temp1[1],xorint(grid[temp2[0]][temp2[1]]))

                            else:
                                raise UnknownError('4-2≠2')
                    #如果四周已统一(不含自己)，就没用了
                    surround=find_neig4(y,x)
                    surroundlist=set([int(grid[temp[0]][temp[1]]) for temp in surround])
                    if len(surroundlist)==1:
                        target[y][x]=None

                case 3:#周围四格仅一个一样的
                    '''
                    策略：
                    与自己有关的：
                    1、周围有两个相同的，则自己相反√
                    2、自己和周围某个相同，则剩下三个直接确定√
                    与自己无关的：
                    3、周围有两个相同的，则剩下两个独立不同√
                    4、周围有两个不同的，则剩下两个独立相同√
                    '''
                    surround=find_neig4(y,x)
                    #统计周围的族
                    surroundlist=[grid[temp[0]][temp[1]] for temp in surround]
                    #先看有没有相同的
                    zuset=set()
                    chongfu=None
                    for temp in surroundlist:
                        if temp not in zuset:
                            zuset.add(temp)
                        else:
                            chongfu=temp
                    if chongfu is not None:#有重复！
                        #自己相反
                        effect+=modify(y,x,int(chongfu),0.5-(chongfu%1))
                        #另外两个被标为不同
                        difflist=[]
                        for temp in surround:
                            if grid[temp[0]][temp[1]]!=chongfu:
                                difflist.append(temp)
                        if len(difflist)==2:
                            effect+=modify(difflist[0][0],difflist[0][1],xorint(grid[difflist[1][0]][difflist[1][1]]))
                    #看看有没有自己和周围相同
                    self=grid[y][x]
                    for temp in surroundlist:
                        if grid[y][x]==temp:#相同!直接进入下阶段
                            for temp in surround:
                                if grid[temp[0]][temp[1]]!=grid[y][x]:
                                    effect+=modify(temp[0],temp[1],xorint(grid[y][x]))
                            break
                    #看看周围有没有两个不同
                    for temp1,temp2 in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3)):
                        if int(surroundlist[temp1])==int(surroundlist[temp2]) and surroundlist[temp1]!=surroundlist[temp2]:#不同！
                            difflist=[temp for temp in range(4) if (temp!=temp1 and temp!=temp2)]
                            if len(difflist)==2:
                                temp1,temp2=surround[difflist[0]],surround[difflist[1]]
                                effect+=modify(temp1[0],temp1[1],grid[temp2[0]][temp2[1]])
                            else:
                                raise UnknownError('4-2≠2')
                            break
                    #如果四周已统一，就没用了
                    surround=find_neig4(y,x)
                    surroundlist=set([int(grid[temp[0]][temp[1]]) for temp in surround+[(y,x)]])
                    if len(surroundlist)==1:
                        target[y][x]=None
                case _:
                    raise UnknownError(f'目标有None和123以外的数，为{target[y][x]}')        

        #小技巧

        #相邻3
        for y, x in product(range(1,height-1), range(1,width-1)):
            if target[y][x]==3:
                surround=find_neig4(y,x)#相邻3：-1 0 1 2各不相同，-1=0*2-1
                for temp in surround:
                    if target[temp[0]][temp[1]]==3:#找到！
                        effect+=modify(y,x,xorint(grid[temp[0]][temp[1]]))#0和1相反
                        effect+=modify(temp[0],temp[1],grid[2*y-temp[0]][2*x-temp[1]])#-1和1相同
                        effect+=modify(y,x,grid[2*temp[0]-y][2*temp[1]-x])#2和0相同
                        break
                
                #斜角3：远处三个各自相同；这里直接硬编码
                if target[y+1][x-1]==3:#找到！是左下-右上，yx是右上
                    effect+=modify(y+2,x-2,grid[y+1][x-2])#左下左边和左下左下
                    effect+=modify(y+2,x-1,grid[y+1][x-2])#左下左边和左下下
                    effect+=modify(y-1,x,grid[y][x+1])
                    effect+=modify(y-1,x+1,grid[y][x+1])
                if target[y+1][x+1]==3:#找到！是左上-右下，yx是左上
                    effect+=modify(y+2,x+1,grid[y+1][x+2])
                    effect+=modify(y+2,x+2,grid[y+1][x+2])
                    effect+=modify(y-1,x,grid[y][x-1])
                    effect+=modify(y-1,x-1,grid[y][x-1])

        #马型2
        ma={(1,0):((-1,-1),(-1,1)),(-1,0):((1,-1),(1,1)),(0,1):((-1,-1),(1,-1)),(0,-1):((-1,1),(1,1))}
        for y, x in product(range(1,height-1), range(1,width-1)):
            if target[y][x]==2:
                zu=grid[y][x]
                surround1=[i for i in find_neig4(y,x) if grid[i[0]][i[1]]==zu]#注释
                if len(surround1)!=1:
                    continue
                surround1=surround1[0]
                delta=(surround1[0]-y,surround1[1]-x)
                surround2=[]
                for i in ma[delta]:
                    surround2.append((i[0]+y,i[1]+x))
                surround2=[i for i in surround2 if grid[i[0]][i[1]]==zu]
                if surround2:
                    for i in surround2:
                        lo=[j for j in find_neig4(y,x) if j!=surround1 and j not in find_neig4(*i)]
                        if len(lo)!=1:
                            raise UnknownError('马步不再是马步！')
                        else:
                            lo=lo[0]
                            effect+=modify(lo[0],lo[1],xorint(zu))

        #3的锅盖头（需国际棋盘引理）
        for y, x in product(range(1,height-1), range(1,width-1)):
            if target[y][x]==3:
                surround1=find_neig8(y,x)
                for i in surround1:
                    surround2=[temp for temp in find_neig4(y,x) if temp in find_neig4(*i)]
                    if xorint(grid[i[0]][i[1]]) == grid[surround2[0][0]][surround2[0][1]] or xorint(grid[i[0]][i[1]]) == grid[surround2[1][0]][surround2[1][1]]:
                        #此时2*0-i、surround2碰不到的两个，共三个必须相同！
                        lo=[temp for temp in find_neig4(y,x) if temp not in find_neig4(*i)]
                        lo.append((2*y-i[0],2*x-i[1]))
                        effect+=modify(lo[0][0],lo[0][1],grid[lo[2][0]][lo[2][1]])
                        effect+=modify(lo[1][0],lo[1][1],grid[lo[2][0]][lo[2][1]])


        #连通性的最实用推论：禁止国际棋盘
        for y, x in product(range(1,height-1), range(1,width-1)):
            tian=((y,x),(y+1,x),(y+1,x+1),(y,x+1))
            tianlist=[grid[temp[0]][temp[1]] for temp in tian]
            tianintlist=list(map(lambda x:int(x),tianlist))
            if len(tianintlist)==1:#统一了，没你事了
                continue
            if tianlist[0]==tianlist[2]:#根据tian硬编码了，但记住这是左上右下对角相等
                if int(tianlist[1])==int(tianlist[0]) and tianlist[1]!=tianlist[0]:#危险，tianlist[3]必须挽回
                    effect+=modify(tian[3][0],tian[3][1],tianlist[0])
                if int(tianlist[3])==int(tianlist[0]) and tianlist[3]!=tianlist[0]:#同样，tianlist[1]必须挽回
                    effect+=modify(tian[1][0],tian[1][1],tianlist[0])
                
            if tianlist[1]==tianlist[3]:#根据tian硬编码了，但记住这是右上左下对角相等
                if int(tianlist[0])==int(tianlist[1]) and tianlist[0]!=tianlist[1]:#危险，tianlist[2]必须挽回
                    effect+=modify(tian[2][0],tian[2][1],tianlist[1])
                if int(tianlist[2])==int(tianlist[1]) and tianlist[2]!=tianlist[1]:#同样，tianlist[0]必须挽回
                    effect+=modify(tian[0][0],tian[0][1],tianlist[1])

        '''
        真正的连通性出场了……
        包含：
        1、冲破封锁
        2、防止闭合
        '''


        #先只更新liantong，而不做出更改
        dellist={1}
        while dellist:
            dellist=set()
            for i in range(len(liantong)):#liantong[i][0]为目前连通的内部，liantong[i][1]为目前连通的四边界
                if i in dellist:
                    continue
                research=liantong[i]
                zu=grid[research[0][0][0]][research[0][0][1]]
                for j in research[1]:
                    if grid[j[0]][j[1]]==zu:#合并
                        #找到j所在的区域
                        for k in range(len(liantong)):
                            if i==k or k in dellist:
                                continue
                            if j in liantong[k][0]:
                                research[0]=list(set(research[0]+liantong[k][0]))
                                research[1]=[p for p in list(set(research[1]+liantong[k][1])) if p not in research[0]]
                                dellist.add(k)#k已经被合并进去了
                                break
            
            dellist=list(dellist)
            dellist.sort(reverse=True)
            #倒序删除
            for i in dellist:
                del liantong[i]
        '''
        冲破封锁：
        1、外界-1全部相反，只有一个未知，则这个未知被同化（最主要）
        2、外界全部独立相同，被同化
        3、外界全部相反，报错
        '''
        for i in liantong:
            kind=set(map(lambda x:grid[x[0]][x[1]],i[1]))
            if len(kind)>2:#太杂了
                continue
            zu=grid[i[0][0][0]][i[0][0][1]]
            if len(kind)==1 and next(iter(kind))!=zu:#外界全同？
                #首先，如果已经全部完成了，那就没这一步了，否则会报错
                win=1
                for y, x in product(range(height), range(width)):
                    if int(grid[y][x])!=0:
                        win=0
                if win:
                    break
                effect+=modify(i[0][0][0],i[1][1][1],next(iter(kind)))
            else:#len==2，触发规则1：统计外圈和zu相反的个数
                situation=None#故技重施
                for j in i[1]:#j是外围的每一个坐标
                    if grid[j[0]][j[1]]!=xorint(zu):
                        if situation is None:
                            situation=j
                        else:
                            situation=None
                            break
                if situation is not None:
                    effect+=modify(situation[0],situation[1],zu)
        '''
        防止闭合：
        只考察0，把所有0去掉后剩余格子显然应该连通
        若将剩余非0.5格子中去掉一个，不再连通，说明这个去掉的格子是重要的枢纽格，只能是0.5
        '''
        #生成所有除0以外格子集合
        gezi_except_0=set()
        for y, x in product(range(height), range(width)):
            if grid[y][x]!=0:
                gezi_except_0.add((y,x))
        for i in gezi_except_0:#遍历每一个0.5以外元素，i是禁忌元素
            if grid[i[0]][i[1]]==0.5:
                continue

            # 剪枝 1：有效邻居太少的不可能是割点
            ne_valid = [nb for nb in find_neig4(*i) if nb in gezi_except_0]
            if len(ne_valid) <= 1:
                continue
            # 找到起点 (避开被抠掉的 i)
            start = ne_valid[0]

            # 剪枝 2：快速测试它的几个邻居之间能否绕开 i 互相连通
            stack = [start]
            flood = {start}
            while stack:
                curr = stack.pop()
                for j in find_neig4(*curr):
                    if j in gezi_except_0 and j not in flood and j != i:
                        flood.add(j)
                        stack.append(j)
            if len(flood)<len(gezi_except_0)-1:
                effect+=modify(i[0],i[1],0.5)




    #只出现一次的区消失
    p={}
    for y, x in product(range(height), range(width)):
        z=int(grid[y][x])
        if z not in p:
            p[z]=1
        else:
            p[z]+=1
    for y, x in product(range(height), range(width)):
        z=int(grid[y][x])
        if p[z]==1:
            grid[y][x]=-1
    
    return width,height,target1,grid


#width, height, target = fetch_loop()


width = 30
height = 30
target = [[None,3,2,2,3,1,2,1,None,None,None,3,3,None,None,None,1,None,1,1,2,None,3,None,None,None,None,None,None,None],[None,None,None,None,None,None,None,None,3,2,2,0,None,2,3,1,None,None,3,None,None,2,None,2,None,3,None,None,2,None],[None,3,2,2,None,2,None,None,None,1,3,None,3,None,None,None,None,1,None,None,3,None,None,None,None,None,None,None,2,None],[None,None,1,None,None,None,2,1,1,None,None,None,None,None,2,3,None,1,None,None,None,None,3,None,None,0,None,1,0,2],[1,2,None,2,2,None,None,None,None,3,2,2,None,2,1,None,None,None,None,2,None,None,3,None,None,0,None,1,None,3],[1,2,None,2,None,None,1,None,None,2,1,1,None,None,2,3,None,2,None,None,3,2,3,None,None,None,None,3,2,None],[2,2,None,2,2,2,None,2,1,2,None,3,None,None,None,None,2,3,None,3,1,None,None,None,None,1,1,3,None,None],[None,None,2,2,None,3,2,None,None,None,None,None,None,None,None,2,3,None,None,None,1,1,None,None,None,None,None,None,1,None],[3,None,None,None,3,2,None,None,None,2,None,2,None,1,None,None,None,2,None,3,1,None,0,None,None,None,None,1,None,3],[None,None,None,None,None,2,3,None,None,0,3,None,None,2,None,None,None,2,None,1,2,None,1,None,None,None,1,None,None,None],[3,3,None,3,None,3,None,0,3,None,2,1,None,3,1,1,None,3,None,3,None,None,None,None,1,1,None,2,None,None],[2,None,3,None,2,None,None,None,3,1,2,None,1,3,None,None,2,None,None,None,2,1,None,None,None,3,None,2,1,None],[None,None,None,None,None,None,3,None,None,None,None,None,None,2,None,None,None,None,None,2,3,1,2,None,None,2,None,None,1,1],[None,None,None,None,None,0,None,1,1,0,2,1,None,None,None,None,3,2,None,None,None,None,None,2,None,2,1,1,None,1],[2,None,None,2,None,1,None,None,1,2,3,2,2,None,1,None,0,None,None,None,None,None,2,None,2,None,None,None,2,3],[3,None,1,1,None,None,None,None,None,2,1,2,None,None,3,None,None,2,None,3,None,None,None,None,2,2,1,None,2,2],[None,None,3,2,None,None,2,None,1,2,2,2,2,None,1,None,None,1,2,None,3,None,3,1,2,1,1,None,None,2],[None,2,None,1,2,None,2,3,3,None,2,2,2,2,2,None,2,None,2,None,None,None,None,None,1,None,None,None,None,2],[None,1,3,2,None,None,None,1,2,2,2,None,1,None,None,2,3,None,None,None,1,1,2,2,None,None,2,1,3,3],[None,None,None,None,3,None,None,None,None,2,None,3,None,None,3,None,None,None,2,2,None,None,None,None,2,None,None,1,None,None],[2,None,3,None,None,2,3,2,2,3,3,1,None,None,None,3,3,2,2,None,None,None,2,None,None,None,None,None,None,2],[3,None,1,None,1,0,None,None,1,1,2,0,1,None,2,None,None,None,None,None,None,3,None,2,None,None,None,1,2,3],[None,1,3,None,1,0,2,None,2,None,None,2,None,None,3,None,None,3,1,3,None,None,2,1,None,None,2,3,None,None],[None,None,3,None,None,1,3,None,2,None,2,1,2,None,None,1,None,None,None,None,2,2,None,None,2,None,None,2,2,None],[2,3,None,None,None,None,None,None,None,None,2,2,None,None,None,1,1,None,None,2,None,None,1,None,None,2,2,3,2,None],[2,2,2,None,None,3,None,None,None,2,None,2,2,1,None,None,None,1,None,1,None,None,3,None,3,None,None,None,None,None],[None,None,None,None,None,None,2,None,2,2,None,None,None,2,None,None,None,None,None,None,3,2,None,1,3,2,2,None,None,None],[None,None,3,3,2,None,None,1,2,2,2,None,None,2,None,None,None,None,3,None,None,2,None,None,None,1,1,None,None,3],[1,None,None,2,None,None,None,None,2,None,None,None,1,0,2,1,1,None,1,None,None,None,2,None,3,1,1,1,None,2],[None,3,3,None,None,2,2,1,None,None,1,None,None,None,None,1,None,None,None,None,None,None,3,2,None,3,None,None,1,2]]

width,height,target,grid=main(width,height,target)

'''虚假的数回：画线成环
真正的数回：把格子染成内外，使得内外都双连通（网格外全是外）；数字代表四边和自己不同的格子数量'''

#把东西都变回去
width-=2
height-=2
grid=[grid[i][1:width+1] for i in range(1,height+1)]
target=[target[i][1:width+1] for i in range(1,height+1)]

#理论上最后应该画线，但懒得画了

show_slitherlink(width, height, target, grid)