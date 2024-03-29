import numpy as np
import plotly.graph_objects as go
from plotly.colors import n_colors
from sklearn.cluster import AgglomerativeClustering
from scipy.stats import mode
from MDAnalysis.analysis import rdf
import MDAnalysis as mda
from scipy.spatial import distance_matrix
from utils import compute_rdf_distance, compute_principal_axes_np
from plotly.subplots import make_subplots
from scipy.ndimage import gaussian_filter1d


def plot_rdf_series(u, nbins, rrange, core_inds, rdf_norm='rdf', n_frames_avg=1):
    total_time = u.trajectory.totaltime
    n_steps = 10
    times = np.arange(0, total_time + 1, total_time // n_steps)

    rdf_analysis = rdf.InterRDF(u.residues[core_inds].atoms, u.atoms, range=rrange, nbins=nbins, verbose=False, norm=rdf_norm)
    n_frames = u.trajectory.n_frames
    rdf_step = n_frames // n_steps

    rdfs = []
    for step in range(0, n_frames, rdf_step):  # range(0, n_frames - 1, rdf_step):
        rdf_analysis.run(start=step, stop=step + n_frames_avg, step=1, verbose=False)
        rdfs.append(rdf_analysis.results.rdf)
    rdfs = np.asarray(rdfs)

    colors = n_colors('rgb(250,50,5)', 'rgb(5,120,200)', len(rdfs), colortype='rgb')
    fig = go.Figure()
    for i in range(len(rdfs)):
        fig.add_scattergl(x=rdf_analysis.results.bins, y=rdfs[i], name=f'{times[i]:.0f} ps', marker=dict(color=colors[i]))

    fig.update_layout(xaxis_title='Range (A)', yaxis_title='Full RDF')

    return fig, rdf_analysis.results.bins, rdfs


def plot_intermolecular_rdf_series(u, nbins, rrange, core_inds, atom_type1=None, atom_type2=None, rdf_norm='rdf', n_frames_avg=1):
    n_molecules = min((100, len(core_inds)))
    randints = np.random.choice(core_inds, size=n_molecules, replace=False)

    rdfs_list = []
    total_time = u.trajectory.totaltime
    n_steps = 10
    times = np.arange(0, total_time + 1, total_time // n_steps)
    for mol_ind in randints:
        mol = u.residues[mol_ind].atoms
        inter_mols = sum([u.residues[ind] for ind in range(len(u.residues)) if ind != mol_ind]).atoms

        if atom_type1 is not None:
            mol = mol.select_atoms("name " + atom_type1)
        if atom_type2 is not None:
            inter_mols = inter_mols.select_atoms("name " + atom_type2)

        rdf_analysis = rdf.InterRDF(mol, inter_mols, range=rrange, nbins=nbins, verbose=False, norm=rdf_norm)
        n_frames = u.trajectory.n_frames
        rdf_step = n_frames // n_steps

        rdfs = []
        for step in range(0, n_frames, rdf_step):  # range(0, n_frames - 1, rdf_step):
            rdf_analysis.run(start=step, stop=step + n_frames_avg, step=1, verbose=False)
            rdfs.append(rdf_analysis.results.rdf)
        rdfs = np.asarray(rdfs)
        rdfs_list.append(rdfs)
    rdfs_list = np.asarray(rdfs_list)  # [molecules, time_steps, rdf_bins]
    combined_rdfs = rdfs_list.mean(0)  # average over molecules

    colors = n_colors('rgb(250,50,5)', 'rgb(5,120,200)', len(combined_rdfs), colortype='rgb')
    fig = go.Figure()
    for i in range(len(combined_rdfs)):
        fig.add_scattergl(x=rdf_analysis.results.bins, y=combined_rdfs[i], name=f'{times[i]:.0f} ps', marker=dict(color=colors[i]))

    fig.update_layout(xaxis_title='Range (A)', yaxis_title='Intermolecular RDF')

    return fig, rdf_analysis.results.bins, combined_rdfs


def plot_cluster_stability(u: mda.Universe):
    mol_size = np.ptp(u.residues[0].atoms.positions)
    clusters_list_list = []
    majority_cluster_list = []
    majority_proportion_list = []
    radii = [4, 5, 6, 7, 8, 10, 12]

    ps_step = 100
    total_time = u.trajectory.totaltime
    times = np.arange(0, total_time + 1, ps_step)

    for cluster_threshold in radii:  # try different cutoffs
        '''identify molecules and assign to inside or outside cluster'''
        clusters_list = []
        majority_cluster = []
        for ts in u.trajectory:
            if ts.time % ps_step == 0:
                molecules = u.residues
                centroids = np.asarray([molecules[i].atoms.centroid() for i in range(len(molecules))])
                clustering = AgglomerativeClustering(linkage='single', metric='euclidean', distance_threshold=cluster_threshold, n_clusters=None).fit(centroids)
                clusters_list.append(clustering.labels_)
                modal, counts = mode(clustering.labels_, keepdims=False)
                majority_cluster.append(modal)
        clusters_list = np.asarray(clusters_list)
        majority_cluster = np.asarray(majority_cluster)
        clusters_list_list.append(clusters_list)
        majority_cluster_list.append(majority_cluster)

        majority_proportion = np.asarray([
            np.average(mols == majority) for mols, majority in zip(clusters_list, majority_cluster)
        ])

        majority_proportion_list.append(majority_proportion)
    #
    # clusters_list_list = np.asarray(clusters_list_list)
    # majority_cluster_list = np.asarray(majority_cluster_list)
    majority_proportion_list_list = np.asarray(majority_proportion_list)

    colors = n_colors('rgb(250,50,5)', 'rgb(5,120,200)', len(majority_proportion_list_list), colortype='rgb')

    fig = go.Figure()
    for i, radius in enumerate(radii):
        fig.add_scattergl(
            x=times, y=majority_proportion_list_list[i],
            name=f'Cutoff {radius:.1f} (A)', fill='tonexty', marker=dict(color=colors[i])
        )
    fig.update_yaxes(range=[-0.05, 1.05])
    fig.update_layout(xaxis_title='Time (ps)', yaxis_title='Proportion in Majority Cluster')

    return fig, times, majority_proportion_list_list


def plot_cluster_centroids_drift(u: mda.Universe):

    ps_step = 100
    total_time = u.trajectory.totaltime
    times = np.arange(0, total_time + 1, ps_step)

    distmat_list = []
    for ts in u.trajectory:
        if ts.time % ps_step == 0:
            molecules = u.residues
            centroids = np.asarray([molecules[i].atoms.centroid() for i in range(len(molecules))])
            distmat_list.append(distance_matrix(centroids, centroids))
    distmat_list = np.asarray(distmat_list)

    distmat_drift = np.zeros(len(distmat_list))
    for i in range(len(distmat_list)):
        distmat_drift[i] = np.sum(np.abs((distmat_list[i] - distmat_list[0]))) / distmat_list[0].sum()

    fig = go.Figure()
    fig.add_scattergl(x=times, y=distmat_drift)
    fig.update_yaxes(range=[-0.05, max(1.05, max(distmat_drift))])
    fig.update_layout(xaxis_title='Time (ps)', yaxis_title='Normed Intermolecular Centroids Drift')

    return fig, times, distmat_drift


def plot_atomwise_rdf_drift(u, atomwise_rdfs, bins):
    t0_atomwise_rdfs = np.asarray([
        rdf[0] for rdf in atomwise_rdfs
    ])
    num_traj_points = len(atomwise_rdfs[0])
    trajectory_atomwise_rdfs = [
        np.asarray([
            rdf[i] for rdf in atomwise_rdfs
        ]) for i in range(1, num_traj_points)
    ]
    rdf_drift = np.zeros(num_traj_points)
    for i in range(1, num_traj_points):
        rdf_drift[i] = compute_rdf_distance(t0_atomwise_rdfs, trajectory_atomwise_rdfs[i - 1], bins)

    ps_step = 100
    total_time = u.trajectory.totaltime
    times = np.arange(0, total_time + 1, ps_step)

    fig = go.Figure()
    fig.add_scattergl(x=times, y=rdf_drift)
    fig.update_yaxes(range=[-0.05, max(1.05, max(rdf_drift))])
    fig.update_layout(xaxis_title='Time (ps)', yaxis_title='Intermolecular Atomwise RDF Drift')

    return fig, times, rdf_drift


def plot_atomwise_rdf_ref_dist(u, atomwise_rdfs, ref_atomwise_rdfs, bins):
    rdf_drift = np.zeros((len(atomwise_rdfs), len(ref_atomwise_rdfs)))
    for i in range(len(atomwise_rdfs)):
        for j in range(len(ref_atomwise_rdfs)):
            rdf_drift[i, j] = compute_rdf_distance(atomwise_rdfs[i], ref_atomwise_rdfs[j], bins, envelope='tanh')

    mean_rdf_drift = rdf_drift.mean(1)  # average over reference trajectory

    return mean_rdf_drift


def cluster_molecule_alignment(u, print_steps=10):
    """
    record the principal inertial vectors for molecules in the cluster
    """
    n_frames = u.trajectory.n_frames
    time_step = u.trajectory.dt

    print_frames = np.arange(0, n_frames, step=n_frames // print_steps)

    Ip_trajectory = np.zeros((len(print_frames), len(u.residues), 3, 3))
    Ip_overlaps_trajectory = np.zeros((len(print_frames), len(u.residues), len(u.residues), 3, 3))
    tind = -1
    for ts in u.trajectory:
        if ts.frame in print_frames:
            tind += 1
            molecules = u.residues
            coords = np.asarray([molecules[i].atoms.positions[:15] for i in range(len(molecules))])  # omit trailing hydrogen in benzamide
            Ip_list = []
            for j in range(len(molecules)):
                Ip, _, _ = compute_principal_axes_np(coords[j])
                Ip_list.append(Ip)

            Ip_list = np.stack(Ip_list)
            Ip_trajectory[tind] = Ip_list

            # source mol, target mol, source Ip, target Ip
            Ip_overlaps = np.zeros((len(molecules), len(molecules), 3, 3))
            for j in range(len(molecules)):
                for k in range(3):
                    Ip_overlaps[j, :, k, :] = Ip_list[j, k].dot(np.transpose(Ip_list, axes=[0, 2, 1]))

            Ip_overlaps_trajectory[tind] = Ip_overlaps

    return Ip_trajectory, Ip_overlaps_trajectory, print_frames


def plot_alignment_fingerprint(u):
    ps_step = 100
    total_time = u.trajectory.totaltime
    times = np.arange(0, total_time + 1, ps_step)

    Ip_overlaps_list = []
    for ts in u.trajectory:
        if ts.time % ps_step == 0:
            molecules = u.residues
            coords = np.asarray([molecules[i].atoms.positions for i in range(len(molecules))])
            Ip_list = []
            for j in range(len(molecules)):
                Ip, _, _ = compute_principal_axes_np(coords[j])
                Ip_list.append(Ip)
            Ip_list = np.stack(Ip_list)

            # source mol, target mol, source Ip, target Ip
            Ip_overlaps = np.zeros((len(molecules), len(molecules), 3, 3))
            for j in range(len(molecules)):
                for k in range(3):
                    Ip_overlaps[j, :, k, :] = Ip_list[j, k].dot(np.transpose(Ip_list, axes=[0, 2, 1]))

            Ip_overlaps_list.append(Ip_overlaps)

    Ip_overlaps_list = np.stack(Ip_overlaps_list)

    Ip_overlaps_drift = np.zeros(len(Ip_overlaps_list))
    for i in range(len(Ip_overlaps_list)):
        Ip_overlaps_drift[i] = np.sum(np.abs((Ip_overlaps_list[i] - Ip_overlaps_list[0]))) / np.prod(list(Ip_overlaps_list[0].shape))  # norm by maximum possible values

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=Ip_overlaps_drift))
    fig.update_yaxes(range=[-0.05, max(1.05, max(Ip_overlaps_drift))])
    fig.update_layout(xaxis_title='Time (ps)', yaxis_title='Normed Molecule Principal Axes Overlap Drift')

    return fig, Ip_overlaps_drift, times


def plot_thermodynamic_data(thermo_results_dict):
    figs = []
    fig = make_subplots(rows=2, cols=3)
    ind = 0
    for i, key in enumerate(thermo_results_dict.keys()):
        if key != 'time step' and key != 'ns_per_day' and key != 'thermo_trajectory':
            ind += 1
            row = ind // 3 + 1
            col = ind % 3 + 1
            fig.add_trace(
                go.Scattergl(x=thermo_results_dict['time step'],
                             y=gaussian_filter1d(thermo_results_dict[key], 5), name=key),
                row=row, col=col
            )
    figs.append(fig)
    if 'thermo_trajectory' in thermo_results_dict.keys():
        thermo_trajectory = thermo_results_dict['thermo_trajectory']
        n_mols = thermo_trajectory.shape[1]
        colors = n_colors('rgb(250,50,5)', 'rgb(5,120,200)', n_mols + 6, colortype='rgb')
        fig = make_subplots(rows=1, cols=3, subplot_titles=['temp', 'kecom', 'internal'])
        for ic in range(3):
            for im in range(n_mols):
                fig.add_trace(
                    go.Scattergl(y=gaussian_filter1d(thermo_trajectory[:, im, ic], 5), marker=dict(color=colors[im]), opacity=.5, name=str(im), showlegend=False),
                    row=1, col=ic + 1)
            fig.add_trace(
                go.Scattergl(y=gaussian_filter1d(thermo_trajectory[:, :, ic].mean(-1), 5), marker=dict(color=colors[im + 5]), opacity=1, showlegend=False),
                row=1, col=ic + 1)
        figs.append(fig)

        colors = n_colors('rgb(250,50,5)', 'rgb(5,120,200)', n_mols + 6, colortype='rgb')
        fig = make_subplots(rows=1, cols=3, subplot_titles=['temp', 'kecom', 'internal'])
        for ic in range(3):
            for im in range(n_mols):
                fig.add_trace(
                    go.Scattergl(y=np.cumsum(thermo_trajectory[:, im, ic]) / np.arange(len(thermo_trajectory)), marker=dict(color=colors[im]), name=str(im), opacity=.5, showlegend=False),
                    row=1, col=ic + 1)
            fig.add_trace(
                go.Scattergl(y=np.cumsum(thermo_trajectory[:, :, ic].mean(-1) / np.arange(len(thermo_trajectory))), marker=dict(color=colors[im + 5]), opacity=1, showlegend=False),
                row=1, col=ic + 1)
        figs.append(fig)
    return figs


def check_for_extra_values(row, extra_axes, extra_values):
    if extra_axes is not None:
        bools = []
        for iv, axis in enumerate(extra_axes):
            bools.append(extra_values[iv] == row[axis])
        return all(bools)
    else:
        return True


def collate_property_over_multiple_runs(target_property, results_df, xaxis, xaxis_title, yaxis, yaxis_title, unique_structures, extra_axes=None, extra_axes_values=None, take_mean=False):
    n_samples = np.zeros((len(unique_structures), len(xaxis), len(yaxis)))

    for iX, xval in enumerate(xaxis):
        for iC, struct in enumerate(unique_structures):
            for iY, yval in enumerate(yaxis):
                for ii, row in results_df.iterrows():
                    if row['structure_identifier'] == struct:
                        if row[xaxis_title] == xval:
                            if row[yaxis_title] == yval:
                                if check_for_extra_values(row, extra_axes, extra_axes_values):
                                    try:
                                        aa = row[target_property]  # see if it's non-empty
                                        n_samples[iC, iX, iY] += 1
                                    except:
                                        pass

    shift_heatmap = np.zeros((len(unique_structures), len(xaxis), len(yaxis)))
    for iX, xval in enumerate(xaxis):
        for iC, struct in enumerate(unique_structures):
            for iY, yval in enumerate(yaxis):
                for ii, row in results_df.iterrows():
                    if row['structure_identifier'] == struct:
                        if row[xaxis_title] == xval:
                            if row[yaxis_title] == yval:
                                if check_for_extra_values(row, extra_axes, extra_axes_values):
                                    try:
                                        if take_mean:
                                            shift_heatmap[iC, iX, iY] += row[target_property].mean() / n_samples[iC, iX, iY]  # take mean over seeds
                                        else:
                                            shift_heatmap[iC, iX, iY] += row[target_property] / n_samples[iC, iX, iY]
                                    except:
                                        shift_heatmap[iC, iX, iY] = 0

    return shift_heatmap, n_samples


def cluster_property_heatmap(results_df, property, xaxis_title, yaxis_title, extra_axes=None, extra_axes_values=None, take_mean=False, norm_against_zero_y=False):
    xaxis = np.unique(results_df[xaxis_title])
    yaxis = np.unique(results_df[yaxis_title])
    unique_structures = np.unique(results_df['structure_identifier'])

    shift_heatmap, n_samples = collate_property_over_multiple_runs(property,
                                                                   results_df, xaxis, xaxis_title, yaxis, yaxis_title, unique_structures,
                                                                   extra_axes=extra_axes, extra_axes_values=extra_axes_values, take_mean=take_mean)

    fig = make_subplots(rows=1, cols=len(unique_structures), subplot_titles=unique_structures)

    for i in range(1, len(unique_structures) + 1):
        if norm_against_zero_y:
            heatmap = shift_heatmap[i - 1] / shift_heatmap[i - 1][:, 0, None]
            max_val, min_val = None, None
        else:
            heatmap = shift_heatmap[i - 1]
            max_val = np.amax(shift_heatmap[i - 1])
            min_val = np.amin(shift_heatmap[i - 1])

        fig.add_trace(go.Heatmap(z=heatmap.T,
                                 text=n_samples[i - 1].T,
                                 texttemplate="%{text}",
                                 colorscale='Viridis', zmax=max_val, zmin=min_val,
                                 ), row=1, col=i)

        fig.update_xaxes(title_text=xaxis_title, row=1, col=i)
        fig.update_yaxes(title_text=yaxis_title, row=1, col=i)

    fig.update_layout(xaxis=dict(
        tickmode='array',
        tickvals=np.arange(len(xaxis)),
        ticktext=xaxis
    ))
    fig.update_layout(yaxis=dict(
        tickmode='array',
        tickvals=np.arange(len(yaxis)),
        ticktext=yaxis
    ))
    if len(unique_structures) > 1:
        fig.update_layout(xaxis2=dict(
            tickmode='array',
            tickvals=np.arange(len(xaxis)),
            ticktext=xaxis
        ))
        fig.update_layout(yaxis2=dict(
            tickmode='array',
            tickvals=np.arange(len(yaxis)),
            ticktext=yaxis
        ))
    if len(unique_structures) > 2:
        fig.update_layout(xaxis3=dict(
            tickmode='array',
            tickvals=np.arange(len(xaxis)),
            ticktext=xaxis
        ))
        fig.update_layout(yaxis3=dict(
            tickmode='array',
            tickvals=np.arange(len(yaxis)),
            ticktext=yaxis
        ))
    fig.update_traces(showscale=False)
    if extra_axes is not None:
        property_name = property + ' ' + str(extra_axes) + ' ' + str(extra_axes_values)
    else:
        property_name = property
    fig.update_layout(title=property_name)
    fig.show(renderer="browser")
    fig.write_image(property + "_heatmap.png")


def plot_classifier_pies(results_df, xaxis_title, yaxis_title, extra_axes=None, extra_axes_values=None):
    xaxis = np.unique(results_df[xaxis_title])
    yaxis = np.unique(results_df[yaxis_title])
    unique_structures = np.unique(results_df['structure_identifier'])
    heatmaps, samples = [], []

    for classo in results_df['NN_classes'][0]:
        shift_heatmap, n_samples = collate_property_over_multiple_runs(
            classo, results_df, xaxis, xaxis_title, yaxis, yaxis_title, unique_structures,
            extra_axes=extra_axes, extra_axes_values=extra_axes_values, take_mean=False)
        heatmaps.append(shift_heatmap)
        samples.append(n_samples)
    heatmaps = np.stack(heatmaps)
    heatmaps = np.transpose(heatmaps, axes=(0, 1, 3, 2))
    samples = np.stack(samples)

    for form_ind, form in enumerate(unique_structures):
        titles = []
        ind = 0
        for i in range(5):
            for j in range(5):
                row = len(yaxis) - ind // len(yaxis) - 1
                col = ind % len(xaxis)
                titles.append(f"{xaxis_title}={xaxis[col]} <br> {yaxis_title}={yaxis[row]}")
                ind += 1

        fig = make_subplots(rows=5, cols=5, subplot_titles=titles,
                            specs=[[{"type": "domain"} for _ in range(5)] for _ in range(5)])

        class_names = ["Form I", "Form II", "Form III", "Form IV", "Form V", "Form VI", "Form VII", "Form VIII", "Form IX", "Liquid"]
        ind = 0
        for i in range(5):
            for j in range(5):
                row = len(yaxis) - ind // len(yaxis)
                col = ind % len(xaxis) + 1
                fig.add_trace(go.Pie(labels=class_names, values=heatmaps[:, form_ind, i, j], sort=False
                                     ),
                              row=row, col=col)
                ind += 1
        fig.update_traces(hoverinfo='label+percent+name', textinfo='none', hole=0.4)
        fig.layout.legend.traceorder = 'normal'
        fig.update_layout(title=form + " Clusters Classifier Outputs")
        fig.update_annotations(font_size=10)

        if extra_axes is not None:
            property_name = form + ' ' + str(extra_axes) + ' ' + str(extra_axes_values)
        else:
            property_name = form
        fig.update_layout(title=property_name)
        fig.show(renderer="browser")
        fig.write_image(form + "_classifier_pies.png")
