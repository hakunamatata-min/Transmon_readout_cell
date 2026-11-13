"""Create presentation figures exclusively from saved project data."""
from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'runtime/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd


def main():
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,
                         'mathtext.fontset':'dejavusans','font.size':12})
    blue, teal, orange = '#14364c', '#156579', '#b35b35'
    fig,ax=plt.subplots(figsize=(11.5,4.5),layout='constrained')
    ax.set(xlim=(0,11.5),ylim=(0,4.5));ax.axis('off')
    def box(x,y,w,h,title,body,color=blue):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.06,rounding_size=0.08',
                                    facecolor='#f0f5f8',edgecolor=color,lw=1.6))
        ax.text(x+w/2,y+h-.25,title,ha='center',va='top',weight='bold',color=color,fontsize=12)
        ax.text(x+w/2,y+h/2-.12,body,ha='center',va='center',color=blue,fontsize=10.5,linespacing=1.7)
    box(.15,1.5,2.0,1.5,'Qiskit Metal','版图与结电感\nWpad：160 / 200 / 240 μm')
    box(2.7,2.55,2.2,1.45,'HFSS 本征模','线性频率与场分布\n不是量子比特的两个能级')
    box(5.45,2.55,2.3,1.45,'EPR + 数值对角化','结参与率与 Josephson 非线性\n跃迁频率、α/h、状态频移')
    box(2.7,.45,2.2,1.45,'HFSS 端口驱动','输入微波，观察输出\n复数 S21 随频率的响应')
    box(5.45,.45,2.3,1.45,'复数 S21 拟合','谐振位置与加载线宽\nΔf、外耦合线宽、Q')
    box(8.35,1.5,2.9,1.5,'设计取舍','状态间隔 / 线宽\n单模 Purcell 寿命估算',orange)
    for a,b in [((2.2,2.4),(2.65,3.2)),((2.2,2.1),(2.65,1.2)),
                ((4.95,3.25),(5.4,3.25)),((4.95,1.2),(5.4,1.2)),
                ((7.8,3.2),(8.3,2.65)),((7.8,1.2),(8.3,1.85))]:
        ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color=teal,lw=1.7))
    fig.savefig(ROOT/'figures/project_workflow.png',dpi=180);plt.close(fig)

    df=pd.read_csv(ROOT/'results/comparison.csv').sort_values('width_um')
    fig,ax=plt.subplots(figsize=(8.5,4.3),layout='constrained')
    ax.plot(df.state_separation_MHz,df.T1_Purcell_estimate_us,'--',color='#a6b5be',lw=1.3)
    for row in df.itertuples():
        chosen=row.width_um==160
        ax.scatter(row.state_separation_MHz,row.T1_Purcell_estimate_us,s=125 if chosen else 75,
                   color=teal if chosen else orange,zorder=3)
        ax.annotate(f'{row.width_um:.0f} μm'+('  验证候选' if chosen else ''),
                    (row.state_separation_MHz,row.T1_Purcell_estimate_us),
                    xytext=(12,-6 if chosen else 10),textcoords='offset points',color=blue,fontsize=11)
    ax.set(xlabel='两状态读出频率间隔（MHz）',ylabel='Purcell 寿命估算（μs）',
           title='更大的状态频率间隔伴随更短的模型寿命',xlim=(3.25,7.35),ylim=(32,78))
    ax.grid(alpha=.18)
    fig.savefig(ROOT/'figures/design_selection.png',dpi=180);plt.close(fig)

    fig,ax=plt.subplots(figsize=(11.5,5.5),layout='constrained');ax.axis('off')
    items=[
        ('Transmon 跃迁与非谐性',r'$E_{10}\simeq\sqrt{8E_cE_J}-E_c,\qquad\alpha=E_{21}-E_{10}\simeq-E_c$','教材式(19.18)、(19.19)，第268页'),
        ('完整状态频率间隔',r'$\omega_{r,g}=\omega_r^{\prime}-\chi,\quad\omega_{r,e}=\omega_r^{\prime}+\chi,\quad\Delta f_{\mathrm{state}}=|2\chi|/(2\pi)$','教材式(22.18)及 Example 22.1，第318页；Δf_state 为本项目补充标签'),
        ('加载线宽',r'$\Delta f=f_r/Q_r=\kappa/(2\pi)$','教材式(24.13)中的频率—Q关系，第351页'),
        ('单模 Purcell 估算（补充模型）',r'$T_{1,\mathrm{P}}\simeq\frac{1}{\kappa_{\mathrm{ext}}}\left|\frac{\hbar\Delta}{g}\right|^2,\qquad\Delta=\omega_q-\omega_r$','g、α 为能量；χ、Δ 为角频率；κext 为能量衰减率')]
    for y,(title,equation,note) in zip([.96,.71,.46,.21],items):
        ax.text(.02,y,title,transform=ax.transAxes,color=blue,fontsize=12,weight='bold',va='top')
        ax.text(.02,y-.065,equation,transform=ax.transAxes,color=teal,fontsize=17,va='top')
        ax.text(.02,y-.155,note,transform=ax.transAxes,color='#536575',fontsize=9.5,va='top')
    fig.savefig(ROOT/'figures/core_formulas.png',dpi=180);plt.close(fig)
    print('Created workflow, candidate-selection and textbook-formula figures.')


if __name__=='__main__':
    main()
