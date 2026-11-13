"""Teaching figure: CPW trace width versus actual qubit coupling-pad width."""
from cell import ROOT, make_cell
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
from matplotlib.font_manager import FontProperties

font=FontProperties(fname=r"C:\Windows\Fonts\msyh.ttc")
plt.rcParams["font.family"]=font.get_name()
plt.rcParams["axes.unicode_minus"]=False

fig,axes=plt.subplots(1,2,figsize=(11,4.9))
ax=axes[0]
ax.set_facecolor("white")
ax.add_patch(Rectangle((0,-30),100,60,color="#222222",zorder=0))
green="#3E9454"
ax.add_patch(Rectangle((0,-30),100,19,color=green))
ax.add_patch(Rectangle((0,-5),100,10,color=green))
ax.add_patch(Rectangle((0,11),100,19,color=green))
for y,label in [(21,"地金属"),(0,"信号金属"),(-21,"地金属")]:
    ax.text(50,y,label,color="white",ha="center",va="center",fontsize=13)
for y0,y1,label,x in [(-5,5,"W = 10 μm",105),(5,11,"S = 6 μm",105),(-11,-5,"S = 6 μm",105)]:
    ax.annotate("",xy=(x,y0),xytext=(x,y1),arrowprops=dict(arrowstyle="<->",color="#243F52",lw=1.2))
    ax.text(x+4,(y0+y1)/2,label,fontsize=10,va="center",color="#243F52")
ax.set(xlim=(-3,145),ylim=(-34,34))
ax.set_title("图 24.3 的 W：CPW 中心导体线宽\n本项目固定为 10 μm",fontsize=12,pad=12)
ax.set_xticks([]);ax.set_yticks([])
ax.text(50,-38,"同一平面的俯视图；黑色为刻蚀掉的间隙",ha="center",va="top",fontsize=10)
for spine in ax.spines.values():
    spine.set_visible(False)

d=make_cell(200)
ax=axes[1]
ax.set_facecolor("#E3E8EB")
tables=d.qgeometry.tables
q_id=d.components["Q1"].id
route_id=d.components["Readout"].id
poly=tables["poly"]
paths=tables["path"]

def add_shape(shape,color,zorder):
    if hasattr(shape,"geoms"):
        for part in shape.geoms:
            add_shape(part,color,zorder)
    else:
        ax.add_patch(Polygon(list(shape.exterior.coords),facecolor=color,edgecolor="none",zorder=zorder))

for _,row in poly[poly.component==q_id].iterrows():
    if row["subtract"]:
        add_shape(row.geometry,"white",1)
for _,row in paths[paths.component.isin([q_id,route_id])].iterrows():
    add_shape(row.geometry.buffer(float(row.width)/2,cap_style=2),"white" if row["subtract"] else "#6A9ABD",2 if row["subtract"] else 3)
for _,row in poly[poly.component==q_id].iterrows():
    if not row["subtract"]:
        add_shape(row.geometry,"#F4A340" if row["name"]=="readout_connector_pad" else "#6A9ABD",4)
pad=poly[(poly.component==q_id)&(poly["name"]=="readout_connector_pad")].iloc[0].geometry
x0,y0,x1,y1=pad.bounds
dim_x=x0-0.035
ax.annotate("",xy=(dim_x,y0),xytext=(dim_x,y1),arrowprops=dict(arrowstyle="<->",color="#BA6613",lw=1.6))
ax.text(dim_x-0.025,(y0+y1)/2,"耦合焊盘宽度 = 200 μm",rotation=90,va="center",ha="center",fontsize=10,color="#A4570B")
ax.plot([-0.815,-0.785],[-0.8,-0.8],color="#253947",lw=1.8,zorder=5)
ax.plot([-0.8],[-0.8],marker="x",color="#253947",markersize=7,zorder=6)
ax.annotate("单个 Josephson 结",xy=(-0.8,-0.8),xytext=(-0.47,-1.09),ha="right",fontsize=10,
    arrowprops=dict(arrowstyle="->",color="#253947"),zorder=10)
ax.annotate("接向读出谐振器",xy=(-0.995,-0.375),xytext=(-0.48,-0.38),ha="right",fontsize=10,
    arrowprops=dict(arrowstyle="->",color="#253947"))
ax.text(-0.48,-0.49,"蓝色：transmon 主电容\n橙色：读出耦合焊盘",ha="right",va="top",fontsize=10,color="#253947",zorder=10)
ax.set(xlim=(-1.2,-0.43),ylim=(-1.15,-0.32),aspect="equal")
ax.set_xticks([]);ax.set_yticks([])
ax.set_title("实际项目的 transmon 局部版图\n扫描橙色焊盘：160 / 200 / 240 μm",fontsize=12,pad=12)
for spine in ax.spines.values():
    spine.set_color("#CED6DC")
fig.tight_layout(w_pad=2.4)
path=ROOT/"figures/explain_cpw_vs_coupling_pad.png"
fig.savefig(path,dpi=180,bbox_inches="tight",facecolor="white")
print(path)
