# %%

import numpy as np
import random


from pathlib import Path
from networkx import MultiGraph, MultiDiGraph, Graph
from networkx.algorithms.euler import eulerian_path
from networkx.algorithms.shortest_paths import shortest_path
from networkx import NetworkXNoPath
from ase import Atoms
from ase.io import read, write
from shppy.atom.basic import radius_query_kdtree, pbc_map
from functools import partial
from shppy.io.lammps import to_tip4p_data

seed = 1234
paths = Path("out/2Dsmall_T175").glob(f"out_45.data")
outs = Path("out/2Dsmall_T175")
ang = 104.52
ang = np.deg2rad(ang)
r = 0.9572
r_c = 3.5

random.seed(seed)
np.random.seed(seed)

for path in paths:
    print(path)
    stru = read(path, format="lammps-data" if path.suffix == ".data" else "extxyz")
    
    # ---
    stru.set_pbc([True, True, False])
    stru.translate([0,0, 16.0])
    stru.wrap()
    # left = stru[stru.numbers != 8]
    # stru = stru[stru.numbers == 8]
    stru.numbers = np.where(stru.numbers == 1, 8, stru.numbers)
    
    assert isinstance(stru, Atoms)
    
    # stru.positions[:, 0:2] += [stru.cell[0,0] / 2, stru.cell[1,1] / 2]
    # stru.set_celldisp([-stru.cell[0,0] / 2,-stru.cell[1,1] / 2, 0])
    # stru.positions[:, 0:2] -= [stru.cell[0,0] / 2, stru.cell[1,1] / 2]
    
    rs = stru.get_positions()
    N = len(rs)
    print("Loaded")
    
    nei = radius_query_kdtree(rs, k = 5, cutoff = r_c, pbc = stru.get_pbc(), cell = stru.cell.array)[1][:,1:]
    pmap = partial(pbc_map, cell = stru.cell.array, pbc=stru.get_pbc(), align_center = True)
    
    G = Graph()
    
    G.add_nodes_from(range(len(rs)))
    
    edges = [(i, int(j), {'count': 0}) for i, neighbors in enumerate(nei) for j in neighbors if i < j and j != len(rs)]

    G.add_edges_from(edges)
    
    for i in G.nodes():
        G.nodes[i]['pos'] = rs[i]

    # print(list(G.degree()))

    H = MultiGraph(G)
    H_degs = list(map(lambda x: x[1], H.degree()))

    extra_nodes = [i for i in H.nodes() if H.degree(i) > 4]

    while extra_nodes != []:
        e = extra_nodes[0]
        nei = list(H.neighbors(e))
        l = max(nei, key=lambda x: np.linalg.norm(pmap(H.nodes[x]['pos'] - H.nodes[e]['pos'])))
        H.remove_edge(e, l)
        extra_nodes = [i for i in H.nodes() if H.degree(i) > 4]

    left_nodes = [i for i in H.nodes() if H.degree(i) < 4]

    while left_nodes != []:
        for i in left_nodes:
            H.add_edge(i, N)

        left_nodes = [i for i in H.nodes() if H.degree(i) < 4]

    paths = list(eulerian_path(H.copy(), random.randint(0, N)))
    paths = np.array([i[0] for i in paths] + [paths[-1][1]])

    for _ in range(9999):
        # print("-", end="")
        i = random.randint(0, N - 1)
        slots = np.where(paths == i)[0]
        p, q = np.random.choice(slots, 2, replace=False)
        p, q = min(p, q), max(p, q)
        paths[p:q+1] = paths[q:p-1 if p > 0 else None:-1]

    paths = zip(paths[:-1], paths[1:])

    J = MultiDiGraph()
    J.add_nodes_from(H.nodes(data=True))
    for i, j in paths:
        J.add_edge(i, j)

    # ---- adjust hdown to hup ----
    selections = [i for i in range(N) if J.nodes[i]['pos'][2] < 2.5]
    donors = [i for i in selections if N in tuple(J.successors(i))]
    fixed_acceptors = [i for i in selections if N in tuple(J.predecessors(i))]
    # if len(valid_acceptors) < len(donors):
    #     print(f"Not enough acceptors for {len(donors)} donors")
    
    rev_J = J.reverse()
    
    print(donors)
    
    for i in donors:
        rev_J.remove_edge(N, i)
    
    for i in fixed_acceptors:
        rev_J.remove_edge(i, N)
        
    for i in donors:
        # print(f"D{i}", end=" ", flush=True)
        try:
            possible_path = shortest_path(rev_J, i, N)
            
        except NetworkXNoPath:
            print(f"No path for {i}")
            break
                
        for u, v in zip(possible_path[:-1], possible_path[1:]):
            rev_J.remove_edge(u, v)
            rev_J.add_edge(v, u)
    

    for i in donors:
        rev_J.add_edge(i, N)
        
    for i in fixed_acceptors:
        rev_J.add_edge(i, N)
    
    J = rev_J.reverse()
    # ----

    rel_pos = {}

    for i in range(len(J) - 1):
        suc = list(J.successors(i))
        pre = list(J.predecessors(i))
        if len(suc) == 1:
            suc = [suc[0], suc[0]]
        if len(pre) == 1:
            pre = [pre[0], pre[0]]
        if suc.count(N) == 2:
            if pre.count(N) == 0:
                # 兩個H都沒有定向, H被其他氫鍵排斥.
                # 配位數為2
                #TODO 如果pre中存在不定向H. 
                this, pre1, pre2 = J.nodes[i]['pos'], J.nodes[pre[0]]['pos'], J.nodes[pre[1]]['pos']
                vec_a = pmap(pre1 - this)
                vec_a /= np.linalg.norm(vec_a)
                vec_b = pmap(pre2 - this)
                vec_b /= np.linalg.norm(vec_b)
                vec_u = np.cross(vec_a, vec_b)
                vec_u /= np.linalg.norm(vec_u)
                vec_v = vec_a + vec_b
                vec_v /= -np.linalg.norm(vec_v)
                
                rel_pos[i] = (
                    (np.cos(ang / 2) * vec_v + np.sin(ang / 2) * vec_u) * r,
                    (np.cos(ang / 2) * vec_v - np.sin(ang / 2) * vec_u) * r,
                )
            elif pre.count(N) == 1:
                this = J.nodes[i]['pos']
                pre1 = J.nodes[pre[0] if pre[0] != N else pre[1]]['pos']
                vec_v = pmap(this - pre1)
                vec_v /= np.linalg.norm(vec_v)
                vec_u = np.cross(vec_v, np.random.rand(3))
                vec_u /= np.linalg.norm(vec_u)

                rel_pos[i] = (
                    (np.cos(ang / 2) * vec_v + np.sin(ang / 2) * vec_u) * r,
                    (np.cos(ang / 2) * vec_v - np.sin(ang / 2) * vec_u) * r,
                )
            else:
                vec_v = np.random.rand(3)
                vec_v /= np.linalg.norm(vec_v)
                vec_u = np.cross(vec_v, np.random.rand(3))
                vec_u /= np.linalg.norm(vec_u)
                
                rel_pos[i] = (
                    (np.cos(ang / 2) * vec_v + np.sin(ang / 2) * vec_u) * r,
                    (np.cos(ang / 2) * vec_v - np.sin(ang / 2) * vec_u) * r,
                )

        elif suc.count(N) == 1 and pre.count(N) <= 1:
            if pre.count(N) == 0:
                # 配位數為3, 2A-1D 構型, 以 D1 為其中一個氫的位置, 另一個則在兩個A的垂直平分面上, 與 D2 成 ang 角, 需要考慮指向問題, D2 與 兩個 A 的角度盡量大.
                this, pre1, pre2 = J.nodes[i]['pos'], J.nodes[pre[0]]['pos'], J.nodes[pre[1]]['pos']
                suc1 = J.nodes[suc[0] if suc[0] != N else suc[1]]['pos']
                
                vec_a = pmap(pre1 - this)
                vec_a /= np.linalg.norm(vec_a)
                vec_b = pmap(pre2 - this)
                vec_b /= np.linalg.norm(vec_b)
                vec_u = np.cross(vec_a, vec_b)
                vec_u /= np.linalg.norm(vec_u)
                vec_v = vec_a + vec_b
                vec_v /= -np.linalg.norm(vec_v)
                
                vec_p = pmap(suc1 - this)
                vec_p = vec_p * r / np.linalg.norm(vec_p)
                b1, b2 = np.dot(vec_p, vec_u), np.dot(vec_p, vec_v)
                phi =  np.arccos(r * np.cos(ang) / np.sqrt(b1**2 + b2**2)) + np.arctan(b1 / b2)
                if np.cos(phi) * b2 < 0:
                    phi = - np.arccos(r * np.cos(ang) / np.sqrt(b1**2 + b2**2)) + np.arctan(b1 / b2)
                vec_q = r * (np.sin(phi) * vec_u + np.cos(phi) * vec_v)
                rel_pos[i] = (vec_p, vec_q)
                
            else:
                # 配位數為2, 1A-1D 構型, 以D為其中一個氫的位置, 另一個則在 AD 平面, 和 A 的反向延長線上成 ang 角.
                this = J.nodes[i]['pos']
                pre1 = J.nodes[pre[0] if pre[0] != N else pre[1]]['pos']
                suc1 = J.nodes[suc[0] if suc[0] != N else suc[1]]['pos']
                vec_a = pmap(pre1 - this)
                vec_a /= np.linalg.norm(vec_a)
                vec_b = pmap(suc1 - this)
                vec_b /= np.linalg.norm(vec_b)
                vec_a = vec_a - np.dot(vec_a, vec_b) * vec_b
                vec_a /= - np.linalg.norm(vec_a)
                rel_pos[i] = (
                    r * vec_b,
                    r * (np.cos(ang) * vec_b + np.sin(ang) * vec_a)
                )
            

        elif suc.count(N) == 1 and pre.count(N) == 2:
            this = J.nodes[i]['pos']
            suc1 = J.nodes[suc[0] if suc[0] != N else suc[1]]['pos']
            
            vec_u = pmap(suc1 - this)
            vec_u /= np.linalg.norm(vec_u)
            
            ran = np.random.rand(3)
            ran /= np.linalg.norm(ran)
            
            vec_v = vec_v - np.dot(vec_v, vec_u) * vec_u
            vec_v /= np.linalg.norm(vec_v)

            rel_pos[i] = (
                r * vec_u,
                r * (np.cos(ang) * vec_u + np.sin(ang) * vec_v)
            )
        
        elif suc.count(N) == 0:
            this, suc1, suc2 = J.nodes[i]['pos'], J.nodes[suc[0]]['pos'], J.nodes[suc[1]]['pos']
            vec_a = pmap(suc1 - this)
            vec_a /= np.linalg.norm(vec_a)
            vec_b = pmap(suc2 - this)
            vec_b /= np.linalg.norm(vec_b)
            vec_u = vec_a - vec_b
            vec_u /= np.linalg.norm(vec_u)
            vec_v = vec_a + vec_b
            vec_v /= np.linalg.norm(vec_v)
            
            rel_pos[i] = (
                r * (np.cos(ang / 2) * vec_v + np.sin(ang / 2) * vec_u),
                r * (np.cos(ang / 2) * vec_v - np.sin(ang / 2) * vec_u),
            )

        else:
            raise ValueError(f"Unknown case: {i}, {suc}, {pre}")

    O_pos = stru.positions
    H1_pos = np.array([rel_pos[i][0] + O_pos[i] for i in rel_pos])
    H2_pos = np.array([rel_pos[i][1] + O_pos[i] for i in rel_pos])

    new_atoms = Atoms(
        numbers=[8, 1, 1] * len(stru),
        positions=np.stack([O_pos, H1_pos, H2_pos], axis = 1).reshape(-1, 3),
        cell=stru.cell.array,
        pbc=stru.pbc,
        celldisp=stru.get_celldisp(),
    )

    # new_atoms += left

    # new_atoms.set_array("id", np.arange(len(new_atoms)))
    # mark = np.zeros(len(new_atoms))
    # mark[np.array(selections) * 3] = 1
    # new_atoms.set_array("mark", mark)

    path.with_stem(path.stem + "_H").with_suffix(".data").write_text(to_tip4p_data(new_atoms))
    # write(path.with_stem(path.stem + "_H").with_suffix(".xyz"), new_atoms)