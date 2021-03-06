import kabuki
import hddm
import numpy as np
import pandas as pd
from numpy.random import rand
from scipy.stats import uniform, norm
from copy import copy
# from hddm.simulators.basic_simulator import simulator_cv
from scipy.special import comb
import itertools


def gen_single_params_set(include=()):
    """Returns a dict of DDM parameters with random values for a singel conditin
    the function is used by gen_rand_params.

        :Optional:
            include : tuple
                Which optional parameters include. Can be
                any combination of:

                * 'z' (bias, default=0.5)
                * 'sv' (inter-trial drift variability)
                * 'sz' (inter-trial bias variability)
                * 'st' (inter-trial non-decision time variability)

                Special arguments are:
                * 'all': include all of the above
                * 'all_inter': include all of the above except 'z'

    """
    params = {}
    if include == "all":
        include = ["z", "sv", "sz", "st"]
    elif include == "all_inter":
        include = ["sv", "sz", "st"]

    params["sv"] = 2.5 * rand() if "sv" in include else 0
    params["sz"] = rand() * 0.4 if "sz" in include else 0
    params["st"] = rand() * 0.35 if "st" in include else 0
    params["z"] = 0.4 + rand() * 0.2 if "z" in include else 0.5

    # Simple parameters
    params["v"] = (rand() - 0.5) * 8
    params["t"] = 0.2 + rand() * 0.3
    params["a"] = 0.5 + rand() * 1.5

    if "pi" in include or "gamma" in include:
        params["pi"] = max(rand() * 0.1, 0.01)
    # params['gamma'] = rand()

    assert hddm.utils.check_params_valid(**params)

    return params


def gen_rand_params(include=(), cond_dict=None, seed=None):
    """Returns a dict of DDM parameters with random values.

    :Optional:
        include : tuple
            Which optional parameters include. Can be
            any combination of:

            * 'z' (bias, default=0.5)
            * 'sv' (inter-trial drift variability)
            * 'sz' (inter-trial bias variability)
            * 'st' (inter-trial non-decision time variability)

            Special arguments are:
            * 'all': include all of the above
            * 'all_inter': include all of the above except 'z'

        cond_dict : dictionary
            cond_dict is used when multiple conditions are desired.
            the dictionary has the form of {param1: [value_1, ... , value_n], param2: [value_1, ... , value_n]}
            and the function will output n sets of parameters. each set with values from the
            appropriate place in the dictionary
            for instance if cond_dict={'v': [0, 0.5, 1]} then 3 parameters set will be created.
            the first with v=0 the second with v=0.5 and the third with v=1.

        seed: float
            random seed

        Output:
            if conditions is None:
                params: dictionary
                    A dictionary holding the parameters values
            else:
                cond_params:
                    A dictionary holding the parameters for each one of the conditions,
                    that has the form {'c1': params1, 'c2': params2, ...}
                    it can be used directly as an argument in gen_rand_data.
                merged_params:
                    A dictionary of parameters that can be used to validate the optimization
                    and learning algorithms.
    """

    # set seed
    if seed is not None:
        np.random.seed(seed)

    # if there is only a single condition then we can use gen_single_params_set
    if cond_dict is None:
        return gen_single_params_set(include=include)

    # generate original parameter set
    org_params = gen_single_params_set(include)

    # create a merged set
    merged_params = org_params.copy()
    for name in cond_dict.keys():
        del merged_params[name]

    cond_params = {}
    n_conds = len(list(cond_dict.values())[0])
    for i in range(n_conds):
        # create a set of parameters for condition i
        # put them in i_params, and in cond_params[c#i]
        i_params = org_params.copy()
        for name in cond_dict.keys():
            i_params[name] = cond_dict[name][i]
            cond_params["c%d" % i] = i_params

            # update merged_params
            merged_params["%s(c%d)" % (name, i)] = cond_dict[name][i]

    return cond_params, merged_params


####################################################################
# Functions to generate RT distributions with specified parameters #
####################################################################


def gen_rts(
        size=1000,
        range_=(-6, 6),
        dt=1e-3,
        intra_sv=1.0,
        structured=True,
        subj_idx=None,
        method="cdf",
        **params
):
    """
    A private function used by gen_rand_data
    Returns a DataFrame of randomly simulated RTs from the DDM.

    :Arguments:
        params : dict
            Parameter names and values to use for simulation.

    :Optional:
        size : int
            Number of RTs to simulate.
        range\_ : tuple
            Minimum (negative) and maximum (positve) RTs.
        dt : float
            Number of steps/sec.
        intra_sv : float
            Intra-trial variability.
        structured : bool
            Return a structured array with fields 'RT'
            and 'response'.
        subj_idx : int
            If set, append column 'subj_idx' with value subj_idx.
        method : str
            Which method to use to simulate the RTs:
                * 'cdf': fast, uses the inverse of cumulative density function to sample, dt can be 1e-2.
                * 'drift': slow, simulates each complete drift process, dt should be 1e-4.

    """
    if "v_switch" in params and method != "drift":
        print(
            "Warning: Only drift method supports changes in drift-rate. v_switch will be ignored."
        )

    # Set optional default values if they are not provided
    for var_param in ("sv", "sz", "st"):
        if var_param not in params:
            params[var_param] = 0
    if "z" not in params:
        params["z"] = 0.5
    if "sv" not in params:
        params["sv"] = 0
    if "sz" not in params:
        params["sz"] = 0

    # # # JY added on 2022-02-17 for factorial
    # # # these are optional
    # for var_param in ("a2", "t2", "z0", "z1", "z2", "v0", "v1", "v2"):
    #     if var_param not in params:
    #         params[var_param] = 0

    # check sample
    if isinstance(
            size, tuple
    ):  # this line is because pymc stochastic use tuple for sample size
        if size == ():
            size = 1
        else:
            size = size[0]

    if method == "cdf_py":
        rts = _gen_rts_from_cdf(params, size, range_, dt)
    elif method == "drift":
        rts = _gen_rts_from_simulated_drift(params, size, dt, intra_sv)[0]
    elif method == "cdf":

        rts = hddm.wfpt.gen_rts_from_cdf(
            params["v"],
            params["sv"],
            params["a"],
            params["z"],
            params["sz"],
            params["t"],
            params["st"],
            size,
            range_[0],
            range_[1],
            dt,
        )

    else:
        raise TypeError("Sampling method %s not found." % method)
    if not structured:
        return rts
    else:
        data = pd.DataFrame(rts, columns=["rt"])
        data["response"] = 1.0
        data["response"][data["rt"] < 0] = 0.0
        data["rt"] = np.abs(data["rt"])

        return data


def _gen_rts_from_simulated_drift(params, samples=1000, dt=1e-4, intra_sv=1.0):
    """Returns simulated RTs from simulating the whole drift-process.

    :Arguments:
        params : dict
            Parameter names and values.

    :Optional:
        samlpes : int
            How many samples to generate.
        dt : float
            How many steps/sec.
        intra_sv : float
            Intra-trial variability.

    :SeeAlso:
        gen_rts
    """

    from numpy.random import rand

    if samples is None:
        samples = 1
    nn = 1000
    a = params["a"]
    v = params["v"]

    if "v_switch" in params:
        switch = True
        t_switch = params["t_switch"] / dt
        # Hack so that we will always step into a switch
        nn = int(round(t_switch))
    else:
        switch = False

    # create delay
    if "st" in params:
        start_delay = (
                uniform.rvs(loc=params["t"], scale=params["st"], size=samples)
                - params["st"] / 2.0
        )
    else:
        start_delay = np.ones(samples) * params["t"]

    # create starting_points
    if "sz" in params:
        starting_points = (
                                  uniform.rvs(loc=params["z"], scale=params["sz"], size=samples)
                                  - params["sz"] / 2.0
                          ) * a
    else:
        starting_points = np.ones(samples) * params["z"] * a

    rts = np.empty(samples)
    step_size = np.sqrt(dt) * intra_sv
    drifts = []

    for i_sample in range(samples):
        drift = np.array([])
        crossed = False
        iter = 0
        y_0 = starting_points[i_sample]
        # drifting...
        if "sv" in params and params["sv"] != 0:
            drift_rate = norm.rvs(v, params["sv"])
        else:
            drift_rate = v

        if "v_switch" in params:
            if "V_switch" in params and params["V_switch"] != 0:
                drift_rate_switch = norm.rvs(params["v_switch"], params["V_switch"])
            else:
                drift_rate_switch = params["v_switch"]

        prob_up = 0.5 * (1 + np.sqrt(dt) / intra_sv * drift_rate)

        while not crossed:
            # Generate nn steps
            iter += 1
            if iter == 2 and switch:
                prob_up = 0.5 * (1 + np.sqrt(dt) / intra_sv * drift_rate_switch)
            position = ((rand(nn) < prob_up) * 2 - 1) * step_size
            position[0] += y_0
            position = np.cumsum(position)
            # Find boundary crossings
            cross_idx = np.where((position < 0) | (position > a))[0]
            drift = np.concatenate((drift, position))
            if cross_idx.shape[0] > 0:
                crossed = True
            else:
                # If not crossed, set last position as starting point
                # for next nn steps to continue drift
                y_0 = position[-1]

        # find the boundary interception
        y2 = position[cross_idx[0]]
        if cross_idx[0] != 0:
            y1 = position[cross_idx[0] - 1]
        else:
            y1 = y_0
        m = (y2 - y1) / dt  # slope
        # y = m*x + b
        b = y2 - m * ((iter - 1) * nn + cross_idx[0]) * dt  # intercept
        if y2 < 0:
            rt = (0 - b) / m
        else:
            rt = (a - b) / m
        rts[i_sample] = (rt + start_delay[i_sample]) * np.sign(y2)

        delay = start_delay[i_sample] / dt
        drifts.append(
            np.concatenate(
                (
                    np.ones(int(delay)) * starting_points[i_sample],
                    drift[: int(abs(rt) / dt)],
                )
            )
        )

    return rts, drifts


def pdf_with_params(rt, params):
    """Helper function that calls full_pdf and gets the parameters
    from the dict params.

    """
    v = params["v"]
    V = params["sv"]
    z = params["z"]
    Z = params["sz"]
    t = params["t"]
    T = params["st"]
    a = params["a"]
    return hddm.wfpt.full_pdf(
        rt,
        v=v,
        V=V,
        a=a,
        z=z,
        Z=Z,
        t=t,
        T=T,
        err=1e-4,
        n_st=2,
        n_sz=2,
        use_adaptive=1,
        simps_err=1e-3,
    )


def _gen_rts_from_cdf(params, samples=1000):
    """Returns simulated RTs sampled from the inverse of the CDF.

    :Arguments:
         params : dict
             Parameter names and values.

     :Optional:
         samples : int
             How many samples to generate.

     :SeeAlso:
         gen_rts

    """
    v = params["v"]
    V = params["sv"]
    z = params["z"]
    Z = params["sz"]
    t = params["t"]
    T = params["st"]
    a = params["a"]
    return hddm.likelihoods.wfpt.ppf(
        np.random.rand(samples), args=(v, V, a, z, Z, t, T)
    )


def gen_rand_data(params=None, n_fast_outliers=0, n_slow_outliers=0, **kwargs):
    """Generate simulated RTs with random parameters.

    :Optional:
         params : dict <default=generate randomly>
             Either dictionary mapping param names to values.

             Or dictionary mapping condition name to parameter
             dictionary (see example below).

             If not supplied, takes random values.

         n_fast_outliers : int <default=0>
             How many fast outliers to add (outlier_RT < ter)

         n_slow_outliers : int <default=0>
             How many late outliers to add.

         The rest of the arguments are forwarded to kabuki.generate.gen_rand_data

    :Returns:
         data array with RTs
         parameter values

    :Example:
         # Generate random data set

         >>> data, params = hddm.generate.gen_rand_data({'v':0, 'a':2, 't':.3},
                                                        size=100, subjs=5)

         # Generate 2 conditions

         >>> data, params = hddm.generate.gen_rand_data({'cond1': {'v':0, 'a':2, 't':.3},
                                                         'cond2': {'v':1, 'a':2, 't':.3}})

    :Notes:
         Wrapper function for kabuki.generate.gen_rand_data. See
         the help doc of that function for more options.
    """

    if params is None:
        params = gen_rand_params()

    from numpy import inf

    # set valid param ranges
    bounds = {
        "a": (0, inf),
        "z": (0, 1),
        "t": (0, inf),
        "st": (0, inf),
        "sv": (0, inf),
        "sz": (0, 1),
    }

    if "share_noise" not in kwargs:
        kwargs["share_noise"] = set(["a", "v", "t", "st", "sz", "sv", "z"])

    # Create RT data
    data, subj_params = kabuki.generate.gen_rand_data(
        gen_rts,
        params,
        check_valid_func=hddm.utils.check_params_valid,
        bounds=bounds,
        **kwargs
    )
    # add outliers
    seed = kwargs.get("seed", None)
    data = add_outliers(data, n_fast=n_fast_outliers, n_slow=n_slow_outliers, seed=seed)

    return data, subj_params


def gen_rand_rlddm_data(
        a,
        t,
        scaler,
        alpha,
        size=1,
        p_upper=1,
        p_lower=0,
        z=0.5,
        q_init=0.5,
        pos_alpha=float("nan"),
        subjs=1,
        split_by=0,
        mu_upper=1,
        mu_lower=0,
        sd_upper=0.1,
        sd_lower=0.1,
        binary_outcome=True,
        uncertainty=False,
):
    all_data = []
    tg = t
    ag = a
    alphag = alpha
    pos_alphag = pos_alpha
    scalerg = scaler
    for s in range(0, subjs):
        t = (
            np.maximum(0.05, np.random.normal(loc=tg, scale=0.05, size=1))
            if subjs > 1
            else tg
        )
        a = (
            np.maximum(0.05, np.random.normal(loc=ag, scale=0.15, size=1))
            if subjs > 1
            else ag
        )
        alpha = (
            np.minimum(
                np.minimum(
                    np.maximum(0.001, np.random.normal(loc=alphag, scale=0.05, size=1)),
                    alphag + alphag,
                ),
                1,
            )
            if subjs > 1
            else alphag
        )
        scaler = (
            np.random.normal(loc=scalerg, scale=0.25, size=1) if subjs > 1 else scalerg
        )
        if np.isnan(pos_alpha):
            pos_alfa = alpha
        else:
            pos_alfa = (
                np.maximum(0.001, np.random.normal(loc=pos_alphag, scale=0.05, size=1))
                if subjs > 1
                else pos_alphag
            )
        n = size
        q_up = np.tile([q_init], n)
        q_low = np.tile([q_init], n)
        response = np.tile([0.5], n)
        feedback = np.tile([0.5], n)
        rt = np.tile([0], n)
        if binary_outcome:
            rew_up = np.random.binomial(1, p_upper, n).astype(float)
            rew_low = np.random.binomial(1, p_lower, n).astype(float)
        else:
            rew_up = np.random.normal(mu_upper, sd_upper, n)
            rew_low = np.random.normal(mu_lower, sd_lower, n)
        sim_drift = np.tile([0], n)
        subj_idx = np.tile([s], n)
        d = {
            "q_up": q_up,
            "q_low": q_low,
            "sim_drift": sim_drift,
            "rew_up": rew_up,
            "rew_low": rew_low,
            "response": response,
            "rt": rt,
            "feedback": feedback,
            "subj_idx": subj_idx,
            "split_by": split_by,
            "trial": 1,
        }
        df = pd.DataFrame(data=d)
        df = df[
            [
                "q_up",
                "q_low",
                "sim_drift",
                "rew_up",
                "rew_low",
                "response",
                "rt",
                "feedback",
                "subj_idx",
                "split_by",
                "trial",
            ]
        ]

        data, params = hddm.generate.gen_rand_data(
            {"a": a, "t": t, "v": df.loc[0, "sim_drift"], "z": z}, subjs=1, size=1
        )
        df.loc[0, "response"] = data.response[0]
        df.loc[0, "rt"] = data.rt[0]
        if data.response[0] == 1.0:
            df.loc[0, "feedback"] = df.loc[0, "rew_up"]
            if df.loc[0, "feedback"] > df.loc[0, "q_up"]:
                alfa = pos_alfa
            else:
                alfa = alpha
        else:
            df.loc[0, "feedback"] = df.loc[0, "rew_low"]
            if df.loc[0, "feedback"] > df.loc[0, "q_low"]:
                alfa = pos_alfa
            else:
                alfa = alpha

        for i in range(1, n):
            df.loc[i, "trial"] = i + 1
            df.loc[i, "q_up"] = (
                                        df.loc[i - 1, "q_up"] * (1 - df.loc[i - 1, "response"])
                                ) + (
                                        (df.loc[i - 1, "response"])
                                        * (
                                                df.loc[i - 1, "q_up"]
                                                + (alfa * (df.loc[i - 1, "rew_up"] - df.loc[i - 1, "q_up"]))
                                        )
                                )
            df.loc[i, "q_low"] = (
                                         df.loc[i - 1, "q_low"] * (df.loc[i - 1, "response"])
                                 ) + (
                                         (1 - df.loc[i - 1, "response"])
                                         * (
                                                 df.loc[i - 1, "q_low"]
                                                 + (alfa * (df.loc[i - 1, "rew_low"] - df.loc[i - 1, "q_low"]))
                                         )
                                 )
            df.loc[i, "sim_drift"] = (df.loc[i, "q_up"] - df.loc[i, "q_low"]) * (scaler)
            data, params = hddm.generate.gen_rand_data(
                {"a": a, "t": t, "v": df.loc[i, "sim_drift"], "z": z}, subjs=1, size=1
            )
            df.loc[i, "response"] = data.response[0]
            df.loc[i, "rt"] = data.rt[0]
            if data.response[0] == 1.0:
                df.loc[i, "feedback"] = df.loc[i, "rew_up"]
                if df.loc[i, "feedback"] > df.loc[i, "q_up"]:
                    alfa = pos_alfa
                else:
                    alfa = alpha
            else:
                df.loc[i, "feedback"] = df.loc[i, "rew_low"]
                if df.loc[i, "feedback"] > df.loc[i, "q_low"]:
                    alfa = pos_alfa
                else:
                    alfa = alpha

        all_data.append(df)
    all_data = pd.concat(all_data, axis=0)
    all_data = all_data[
        [
            "q_up",
            "q_low",
            "sim_drift",
            "response",
            "rt",
            "feedback",
            "subj_idx",
            "split_by",
            "trial",
        ]
    ]

    return all_data


# JY added on 2022-02-17

# def wienerRL_like_2step_reg(x, v0, v1, v2, z0, z1, z2,lambda_, 
# alpha, pos_alpha, gamma, a,z,t,v, a_2, z_2, t_2,v_2,alpha2, qval,
# two_stage, w, p_outlier=0): # regression ver2: bounded, a fixed to 1
#

def simulation(
        # x_train,  # this is the dataframe of data of the given participant
        x,
        # fold,
        # size=1,
        # p_upper=1,
        # p_lower=0,
        # # z=0.5,
        # q_init=0.5,
        # # pos_alpha=float("nan"),
        # # subjs=1,
        # split_by=0,
        # mu_upper=1,
        # mu_lower=0,
        # sd_upper=0.1,
        # sd_lower=0.1,
        # binary_outcome=True,
        # uncertainty=False,
        **kwargs
):
    # Receiving behavioral data
    total_x_len = len(x)  # total length of data

    # nstates = max(x_train["state2"].values.astype(int)) + 1

    subjs = len(np.unique(x["subj_idx"]))
    q = x["q_init"].iloc[0]

    rt1 = x["rt1"].values
    rt2 = x["rt2"].values
    responses1 = x["response1"].values.astype(int)
    responses2 = x["response2"].values.astype(int)
    s1s = x["state1"].values.astype(int)
    s2s = x["state2"].values.astype(int)


    q = x["q_init"].iloc[0]
    feedback = x["feedback"].values.astype(float)
    split_by = x["split_by"].values.astype(int)

    # JY added for two-step tasks on 2021-12-05
    nstates = max(x["state2"].values.astype(int)) + 1

    subjs = len(np.unique(x["subj_idx"]))

    # Receiving all keyword arguments
    a = kwargs.pop("a", 1) # return 1 as default (if not otherwise specified)
    a_2 = kwargs.pop("a_2", 1) # return 1 as default (if not otherwise specified)
    t = kwargs.pop("t", False)
    t_2 = kwargs.pop("t_2", False)
    v0 = kwargs.pop("v0", False)
    v1 = kwargs.pop("v1", False)
    v2 = kwargs.pop("v2", False)
    v_interaction = kwargs.pop("v_interaction", False)
    v_2 = kwargs.pop("v_2", False)
    z = kwargs.pop("z", 0.5) # return 0.5 as default (if not otherwise specified)
    z0 = kwargs.pop("z0", False)
    z1 = kwargs.pop("z1", False)
    z2 = kwargs.pop("z2", False)
    z_interaction = kwargs.pop("z_interaction", False)
    z_2 = kwargs.pop("z_2", 0.5)
    lambda_ = kwargs.pop("lambda_", False)  # float("nan")
    gamma = kwargs.pop("gamma", False)
    w = kwargs.pop("w", False)
    w2 = kwargs.pop("w2", False)
    scaler = kwargs.pop("scaler", False)
    scaler2 = kwargs.pop("scaler_2", False)
    z_scaler = kwargs.pop("z_scaler", False)
    pos_alpha = kwargs.pop("pos_alpha", False)
    alpha = kwargs.pop("alpha", False)
    alpha2 = kwargs.pop("alpha2", False)

    all_data_response = []
    all_data_rt = []
    all_data_response1 = []
    all_data_rt1 = []
    all_data_response2 = []
    all_data_rt2 = []
    tg = t
    ag = a
    tg2 = t_2
    ag2 = a_2

    alphag = alpha
    alphag2 = alpha2

    pos_alphag = pos_alpha
    scalerg = scaler
    scalerg2 = scaler2
    z_scalerg = z_scaler

    Tm = np.array([[0.7, 0.3], [0.3, 0.7]])  # transition matrix

    for s in range(0, subjs):
        # if
        t = (
            np.maximum(0.05, np.random.normal(loc=tg, scale=0.05, size=1))
            if subjs > 1
            else tg
        )

        a = (
            np.maximum(0.05, np.random.normal(loc=ag, scale=0.15, size=1))
            if subjs > 1
            else ag
        )

        alpha = (
            np.minimum(
                np.minimum(
                    np.maximum(0.001, np.random.normal(loc=alphag, scale=0.05, size=1)),
                    alphag + alphag,
                ),
                1,
            )
            if subjs > 1
            else alphag
        )

        scaler = (
            np.random.normal(loc=scalerg, scale=0.25, size=1) if subjs > 1 else scalerg
        )
        z_scaler = (
            np.random.normal(loc=z_scalerg, scale=0.25, size=1) if subjs > 1 else z_scalerg
        )

        if np.isnan(pos_alpha):
            pos_alfa = alpha
        else:
            pos_alfa = (
                np.maximum(0.001, np.random.normal(loc=pos_alphag, scale=0.05, size=1))
                if subjs > 1
                else pos_alphag
            )
        # n = size
        n = len(x)
        # if two_stage:
        if t_2:
            t_2 = (
                np.maximum(0.05, np.random.normal(loc=tg2, scale=0.05, size=1))
                if subjs > 1
                else tg2
            )
        if a_2:
            a_2 = (
                np.maximum(0.05, np.random.normal(loc=ag2, scale=0.15, size=1))
                if subjs > 1
                else ag2
            )
        if alpha2:
            alpha2 = (
                np.minimum(
                    np.minimum(
                        np.maximum(0.001, np.random.normal(loc=alphag2, scale=0.05, size=1)),
                        alphag + alphag,
                    ),
                    1,
                )
                if subjs > 1
                else alphag2
            )
        if scaler2:
            scaler2 = (
                np.random.normal(loc=scalerg2, scale=0.25, size=1) if subjs > 1 else scalerg2
            )


        qs_mf = np.ones((comb(nstates, 2, exact=True), 2)) * q  # first-stage MF Q-values
        qs_mb = np.ones((nstates, 2)) * q  # second-stage Q-values

        if alpha:
            alfa = (2.718281828459 ** alpha) / (1 + 2.718281828459 ** alpha)
        if gamma:
            gamma_ = (2.718281828459 ** gamma) / (1 + 2.718281828459 ** gamma)
        if alpha2:
            alfa2 = (2.718281828459 ** alpha2) / (1 + 2.718281828459 ** alpha2)
        else:
            alfa2 = alfa
        if lambda_:
            lambda__ = (2.718281828459 ** lambda_) / (1 + 2.718281828459 ** lambda_)
        if w:
            w = (2.718281828459 ** w) / (1 + 2.718281828459 ** w)
        if w2:
            w2 = (2.718281828459 ** w2) / (1 + 2.718281828459 ** w2)

        state_combinations = np.array(list(itertools.combinations(np.arange(nstates), 2)))

        for j in range(total_x_len):  # loop over total data, including train

            # FIRST STAGE
            planets = state_combinations[s1s[j]]

            # dtq = qs[1] - qs[0]
            Qmb = np.dot(Tm, [np.max(qs_mb[planets[0], :]), np.max(qs_mb[planets[1], :])])

            dtq_mb = Qmb[1] - Qmb[0]
            dtq_mf = qs_mf[s1s[j], 1] - qs_mf[s1s[j], 0]

            # if v0:  # if use v regression
            #     v_ = v0 + (dtq_mb * v1) + (dtq_mf * v2) + (v_interaction * dtq_mb * dtq_mf)
            #
            # else:  # if don't use v regression
            #     v_ = scaler
            if w: # use w scaling for drift rate
                qs = w * Qmb + (1 - w) * qs_mf[s1s[j], :]  # Update for 1st trial
                dtq = qs[1] - qs[0]
                v_ = dtq * scaler
            if w2: # use w scaling for starting point
                qs = w2 * Qmb + (1 - w2) * qs_mf[s1s[j], :]  # Update for 1st trial
                dtq = qs[1] - qs[0]
                z_ = dtq * z_scaler
                sig = 1 / (1 + np.exp(-z_))

            # if z0:
            #     z_ = z0 + (dtq_mb * z1) + (dtq_mf * z2) + (z_interaction * dtq_mb * dtq_mf)
            #     sig = 1 / (1 + np.exp(-z_))
            # else:
            #     sig = z

                # rt = x1s[i]

            # if isleft1s[i] == 0: # if chosen right
            #     rt = -rt
            #     v_ = -v_
            # x = simulator_cv([v_, a, sig, t])

            data1, params1 = hddm.generate.gen_rand_data(
                {"a": a, "t": t, "v": v_, "z": sig},
                # subjs=1, size=1
                size=1000, subjs=1  # make 1,000 simulations?
            )
            # SECOND STAGE
            if t_2: # if second stage; whether or not other parameters are used, t_2 is always used if 2nd stage is estimated
                qs = qs_mb[s2s[j], :]
                dtq = qs[1] - qs[0]
                v_ = dtq * v_2
                # if isleft2_test[j] == 0:  # if chosen right
                #     v_ = -v_
                sig = z_2
                data2, params2 = hddm.generate.gen_rand_data(
                    {"a": a_2, "t": t_2, "v": v_, "z": sig},
                    # subjs=1, size=1
                    size=1000, subjs=1  # make 1,000 simulations?
                )
                all_data_rt2.append(data2.rt)
                all_data_response2.append(data2.response)

            # Update test fold
            dtQ1 = qs_mb[s2s[j], responses2[j]] - qs_mf[
                s1s[j], responses1[j]]  # delta stage 1
            qs_mf[s1s[j], responses1[j]] = qs_mf[s1s[j], responses1[
                j]] + alfa * dtQ1  # delta update for qmf

            dtQ2 = feedback[j] - qs_mb[s2s[j], responses2[j]]  # delta stage 2
            qs_mb[s2s[j], responses2[j]] = qs_mb[s2s[j], responses2[
                j]] + alfa2 * dtQ2  # delta update for qmb
            if lambda_:  # if using eligibility trace
                qs_mf[s1s[j], responses1[j]] = qs_mf[s1s[j], responses1[
                    j]] + lambda__ * dtQ2  # eligibility trace

            # memory decay for unexperienced options in this trial
            if gamma:
                for s_ in range(nstates):
                    for a_ in range(2):
                        if (s_ is not s2s[j]) or (a_ is not responses2[j]):
                            # qs_mb[s_, a_] = qs_mb[s_, a_] * (1-gamma)
                            qs_mb[s_, a_] *= (1 - gamma_)

                for s_ in range(comb(nstates, 2, exact=True)):
                    for a_ in range(2):
                        if (s_ is not s1s[j]) or (a_ is not responses1[j]):
                            qs_mf[s_, a_] *= (1 - gamma_)
            all_data_rt1.append(data1.rt)
            all_data_response1.append(data1.response)

        all_data_rt.append(all_data_rt1)
        all_data_response.append(all_data_response1)
        if t_2:  # if 2nd stage is also estimated:
            all_data_rt.append(all_data_rt2)
            all_data_response.append(all_data_response2)


    # return all_data
    return all_data_response, all_data_rt


# For now, only one participant only
def cross_validation(
        x_train,  # this is the dataframe of data of the given participant
        x_test,
        fold,
        # size=1,
        # p_upper=1,
        # p_lower=0,
        # # z=0.5,
        # q_init=0.5,
        # # pos_alpha=float("nan"),
        # # subjs=1,
        # split_by=0,
        # mu_upper=1,
        # mu_lower=0,
        # sd_upper=0.1,
        # sd_lower=0.1,
        # binary_outcome=True,
        # uncertainty=False,
        **kwargs
):
    # Receiving behavioral data
    total_x_len = len(x_train) + len(x_test)  # total length of data

    rt1_train = x_train["rt1"].values
    rt2_train = x_train["rt2"].values
    responses1_train = x_train["response1"].values.astype(int)
    responses2_train = x_train["response2"].values.astype(int)
    s1s_train = x_train["state1"].values.astype(int)
    s2s_train = x_train["state2"].values.astype(int)

    isleft1_train = x_train["isleft1"].values.astype(int)
    isleft2_train = x_train["isleft2"].values.astype(int)

    q_train = x_train["q_init"].iloc[0]
    feedback_train = x_train["feedback"].values.astype(float)
    split_by_train = x_train["split_by"].values.astype(int)

    # JY added for two-step tasks on 2021-12-05
    # nstates = x["nstates"].values.astype(int)
    nstates = max(x_train["state2"].values.astype(int)) + 1

    subjs = len(np.unique(x_train["subj_idx"]))
    q = x_train["q_init"].iloc[0]

    rt1_test = x_test["rt1"].values
    rt2_test = x_test["rt2"].values
    responses1_test = x_test["response1"].values.astype(int)
    responses2_test = x_test["response2"].values.astype(int)
    s1s_test = x_test["state1"].values.astype(int)
    s2s_test = x_test["state2"].values.astype(int)

    isleft1_test = x_test["isleft1"].values.astype(int)
    isleft2_test = x_test["isleft2"].values.astype(int)

    q_test = x_test["q_init"].iloc[0]
    feedback_test = x_test["feedback"].values.astype(float)
    split_by_test = x_test["split_by"].values.astype(int)

    # JY added for two-step tasks on 2021-12-05
    # nstates = x["nstates"].values.astype(int)
    nstates_test = max(x_test["state2"].values.astype(int)) + 1

    subjs_test = len(np.unique(x_test["subj_idx"]))
    q_test = x_test["q_init"].iloc[0]

    # Receiving all keyword arguments
    a = kwargs.pop("a", 1) # return 1 as default (if not otherwise specified)
    a_2 = kwargs.pop("a_2", 1) # return 1 as default (if not otherwise specified)
    t = kwargs.pop("t", False)
    t_2 = kwargs.pop("t_2", False)
    v0 = kwargs.pop("v0", False)
    v1 = kwargs.pop("v1", False)
    v2 = kwargs.pop("v2", False)
    v_interaction = kwargs.pop("v_interaction", False)
    v_2 = kwargs.pop("v_2", False)
    z = kwargs.pop("z", 0.5) # return 0.5 as default (if not otherwise specified)
    z0 = kwargs.pop("z0", False)
    z1 = kwargs.pop("z1", False)
    z2 = kwargs.pop("z2", False)
    z_interaction = kwargs.pop("z_interaction", False)
    z_2 = kwargs.pop("z_2", 0.5)
    lambda_ = kwargs.pop("lambda_", False)  # float("nan")
    gamma = kwargs.pop("gamma", False)
    w = kwargs.pop("w", False)
    w2 = kwargs.pop("w2", False)
    scaler = kwargs.pop("scaler", False)
    z_scaler = kwargs.pop("z_scaler", False)
    scaler2 = kwargs.pop("scaler_2", False)
    pos_alpha = kwargs.pop("pos_alpha", False)
    alpha = kwargs.pop("alpha", False)
    alpha2 = kwargs.pop("alpha2", False)

    all_data_response = []
    all_data_rt = []
    all_data_response1 = []
    all_data_rt1 = []
    all_data_response2 = []
    all_data_rt2 = []
    tg = t
    ag = a
    tg2 = t_2
    ag2 = a_2

    alphag = alpha
    alphag2 = alpha2

    pos_alphag = pos_alpha
    scalerg = scaler
    z_scalerg = z_scaler

    scalerg2 = scaler2

    Tm = np.array([[0.7, 0.3], [0.3, 0.7]])  # transition matrix

    for s in range(0, subjs):
        # if 
        t = (
            np.maximum(0.05, np.random.normal(loc=tg, scale=0.05, size=1))
            if subjs > 1
            else tg
        )

        a = (
            np.maximum(0.05, np.random.normal(loc=ag, scale=0.15, size=1))
            if subjs > 1
            else ag
        )

        alpha = (
            np.minimum(
                np.minimum(
                    np.maximum(0.001, np.random.normal(loc=alphag, scale=0.05, size=1)),
                    alphag + alphag,
                ),
                1,
            )
            if subjs > 1
            else alphag
        )

        scaler = (
            np.random.normal(loc=scalerg, scale=0.25, size=1) if subjs > 1 else scalerg
        )

        if np.isnan(pos_alpha):
            pos_alfa = alpha
        else:
            pos_alfa = (
                np.maximum(0.001, np.random.normal(loc=pos_alphag, scale=0.05, size=1))
                if subjs > 1
                else pos_alphag
            )
        # n = size
        n = len(x_test)
        # if two_stage: 
        if t_2:
            t_2 = (
                np.maximum(0.05, np.random.normal(loc=tg2, scale=0.05, size=1))
                if subjs > 1
                else tg2
            )
        if a_2:
            a_2 = (
                np.maximum(0.05, np.random.normal(loc=ag2, scale=0.15, size=1))
                if subjs > 1
                else ag2
            )
        if alpha2:
            alpha2 = (
                np.minimum(
                    np.minimum(
                        np.maximum(0.001, np.random.normal(loc=alphag2, scale=0.05, size=1)),
                        alphag2 + alphag2,
                    ),
                    1,
                )
                if subjs > 1
                else alphag2
            )
        if scaler2:
            scaler2 = (
                np.random.normal(loc=scalerg2, scale=0.25, size=1) if subjs > 1 else scalerg2
            )
        if z_scaler:
            z_scaler = (
                np.random.normal(loc=z_scalerg, scale=0.25, size=1) if subjs > 1 else z_scalerg
            )

        qs_mf = np.ones((comb(nstates, 2, exact=True), 2)) * q  # first-stage MF Q-values
        qs_mb = np.ones((nstates, 2)) * q  # second-stage Q-values

        if alpha:
            alfa = (2.718281828459 ** alpha) / (1 + 2.718281828459 ** alpha)
        if gamma:
            gamma_ = (2.718281828459 ** gamma) / (1 + 2.718281828459 ** gamma)
        if alpha2:
            alfa2 = (2.718281828459 ** alpha2) / (1 + 2.718281828459 ** alpha2)
        else:
            alfa2 = alfa
        if lambda_:
            lambda__ = (2.718281828459 ** lambda_) / (1 + 2.718281828459 ** lambda_)
        if w:
            w = (2.718281828459 ** w) / (1 + 2.718281828459 ** w)
        if w2:
            w2 = (2.718281828459 ** w2) / (1 + 2.718281828459 ** w2)
        state_combinations = np.array(list(itertools.combinations(np.arange(nstates), 2)))

        for counter in range(total_x_len):  # loop over total data, including train
            i = -1
            j = -1

            if counter % 10 != fold:  # TRAIN trial: do q-value updating only

                i += 1

                dtQ1 = qs_mb[s2s_train[i], responses2_train[i]] - qs_mf[
                    s1s_train[i], responses1_train[i]]  # delta stage 1
                qs_mf[s1s_train[i], responses1_train[i]] = qs_mf[s1s_train[i], responses1_train[
                    i]] + alfa * dtQ1  # delta update for qmf

                dtQ2 = feedback_train[i] - qs_mb[s2s_train[i], responses2_train[i]]  # delta stage 2
                qs_mb[s2s_train[i], responses2_train[i]] = qs_mb[s2s_train[i], responses2_train[
                    i]] + alfa2 * dtQ2  # delta update for qmb
                if lambda_:  # if using eligibility trace
                    qs_mf[s1s_train[i], responses1_train[i]] = qs_mf[s1s_train[i], responses1_train[
                        i]] + lambda__ * dtQ2  # eligibility trace

                # memory decay for unexperienced options in this trial
                if gamma:
                    for s_ in range(nstates):
                        for a_ in range(2):
                            if (s_ is not s2s_train[i]) or (a_ is not responses2_train[i]):
                                # qs_mb[s_, a_] = qs_mb[s_, a_] * (1-gamma)
                                qs_mb[s_, a_] *= (1 - gamma_)

                    for s_ in range(comb(nstates, 2, exact=True)):
                        for a_ in range(2):
                            if (s_ is not s1s_train[i]) or (a_ is not responses1_train[i]):
                                qs_mf[s_, a_] *= (1 - gamma_)

                # counter[s1s_train[i]] += 1

            else:  # TEST: do the RT/choice simulation
                j += 1

                # FIRST STAGE
                planets = state_combinations[s1s_test[j]]

                # dtq = qs[1] - qs[0]
                Qmb = np.dot(Tm, [np.max(qs_mb[planets[0], :]), np.max(qs_mb[planets[1], :])])

                dtq_mb = Qmb[1] - Qmb[0]
                dtq_mf = qs_mf[s1s_test[j], 1] - qs_mf[s1s_test[j], 0]

                if v0:  # if use v regression
                    v_ = v0 + (dtq_mb * v1) + (dtq_mf * v2) + (v_interaction * dtq_mb * dtq_mf)

                # else:  # if don't use v regression
                #     v_ = scaler

                # if isleft1_test[j] == 0: # if chosen right
                #     v_ = -v_

                if z0:
                    z_ = z0 + (dtq_mb * z1) + (dtq_mf * z2) + (z_interaction * dtq_mb * dtq_mf)
                    sig = 1 / (1 + np.exp(-z_))
                # else:
                #     sig = z
                if w:  # use w scaling for drift rate
                    qs = w * Qmb + (1 - w) * qs_mf[s1s_test[j], :]  # Update for 1st trial
                    dtq = qs[1] - qs[0]
                    v_ = dtq * scaler
                if w2:  # use w scaling for starting point
                    qs = w2 * Qmb + (1 - w2) * qs_mf[s1s_test[j], :]  # Update for 1st trial
                    dtq = qs[1] - qs[0]
                    z_ = dtq * z_scaler
                    sig = 1 / (1 + np.exp(-z_))
                    # rt = x1s[i]

                # if isleft1s[i] == 0: # if chosen right
                #     rt = -rt
                #     v_ = -v_
                # x = simulator_cv([v_, a, sig, t])

                data1, params1 = hddm.generate.gen_rand_data(
                    {"a": a, "t": t, "v": v_, "z": sig},
                    # subjs=1, size=1
                    size=1000, subjs=1  # make 1,000 simulations?
                )
                # SECOND STAGE
                if t_2: # if second stage; whether or not other parameters are used, t_2 is always used if 2nd stage is estimated
                    qs = qs_mb[s2s_test[j], :]
                    dtq = qs[1] - qs[0]
                    v_ = dtq * v_2
                    # if isleft2_test[j] == 0:  # if chosen right
                    #     v_ = -v_
                    sig = z_2
                    data2, params2 = hddm.generate.gen_rand_data(
                        {"a": a_2, "t": t_2, "v": v_, "z": sig},
                        # subjs=1, size=1
                        size=1000, subjs=1  # make 1,000 simulations?
                    )
                    all_data_rt2.append(data2.rt)
                    all_data_response2.append(data2.response)

                # Update test fold
                dtQ1 = qs_mb[s2s_test[j], responses2_test[j]] - qs_mf[
                    s1s_test[j], responses1_test[j]]  # delta stage 1
                qs_mf[s1s_test[j], responses1_test[j]] = qs_mf[s1s_test[j], responses1_test[
                    j]] + alfa * dtQ1  # delta update for qmf

                dtQ2 = feedback_test[j] - qs_mb[s2s_test[j], responses2_test[j]]  # delta stage 2
                qs_mb[s2s_test[j], responses2_test[j]] = qs_mb[s2s_test[j], responses2_test[
                    j]] + alfa2 * dtQ2  # delta update for qmb
                if lambda_:  # if using eligibility trace
                    qs_mf[s1s_test[j], responses1_test[j]] = qs_mf[s1s_test[j], responses1_test[
                        j]] + lambda__ * dtQ2  # eligibility trace

                # memory decay for unexperienced options in this trial
                if gamma:
                    for s_ in range(nstates):
                        for a_ in range(2):
                            if (s_ is not s2s_test[j]) or (a_ is not responses2_test[j]):
                                # qs_mb[s_, a_] = qs_mb[s_, a_] * (1-gamma)
                                qs_mb[s_, a_] *= (1 - gamma_)

                    for s_ in range(comb(nstates, 2, exact=True)):
                        for a_ in range(2):
                            if (s_ is not s1s_test[j]) or (a_ is not responses1_test[j]):
                                qs_mf[s_, a_] *= (1 - gamma_)
                all_data_rt1.append(data1.rt)
                all_data_response1.append(data1.response)

        all_data_rt.append(all_data_rt1)
        all_data_response.append(all_data_response1)
        if t_2:  # if 2nd stage is also estimated:
            all_data_rt.append(all_data_rt2)
            all_data_response.append(all_data_response2)


    # return all_data
    return all_data_response, all_data_rt


def gen_rand_rl_data(
        scaler,
        alpha,
        size=1,
        p_upper=1,
        p_lower=0,
        z=0.5,
        q_init=0.5,
        pos_alpha=float("nan"),
        subjs=1,
        split_by=0,
        mu_upper=1,
        mu_lower=0,
        sd_upper=0.1,
        sd_lower=0.1,
        binary_outcome=True,
):
    all_data = []
    alphag = alpha
    pos_alphag = pos_alpha
    scalerg = scaler
    for s in range(0, subjs):
        alpha = (
            np.minimum(
                np.minimum(
                    np.maximum(0.001, np.random.normal(loc=alphag, scale=0.05, size=1)),
                    alphag + alphag,
                ),
                1,
            )
            if subjs > 1
            else alphag
        )
        scaler = (
            np.random.normal(loc=scalerg, scale=0.25, size=1) if subjs > 1 else scalerg
        )
        if np.isnan(pos_alpha):
            pos_alfa = alpha
        else:
            pos_alfa = (
                np.maximum(0.001, np.random.normal(loc=pos_alphag, scale=0.05, size=1))
                if subjs > 1
                else pos_alphag
            )
        n = size
        q_up = np.tile([q_init], n)  # initialize q
        q_low = np.tile([q_init], n)  # initialize q
        response = np.tile([0.5], n)
        feedback = np.tile([0.5], n)
        rt = np.tile([0], n)
        if binary_outcome:
            rew_up = np.random.binomial(1, p_upper, n).astype(float)
            rew_low = np.random.binomial(1, p_lower, n).astype(float)
        else:
            rew_up = np.random.normal(mu_upper, sd_upper, n)
            rew_low = np.random.normal(mu_lower, sd_lower, n)
        sim_drift = np.tile([0], n)
        p = np.tile([0.5], n)
        subj_idx = np.tile([s], n)
        d = {
            "q_up": q_up,
            "q_low": q_low,
            "p": p,
            "sim_drift": sim_drift,
            "rew_up": rew_up,
            "rew_low": rew_low,
            "response": response,
            "feedback": feedback,
            "subj_idx": subj_idx,
            "split_by": split_by,
            "trial": 1,
        }
        df = pd.DataFrame(data=d)
        df = df[
            [
                "q_up",
                "q_low",
                "p",
                "sim_drift",
                "rew_up",
                "rew_low",
                "response",
                "feedback",
                "subj_idx",
                "split_by",
                "trial",
            ]
        ]
        if df.loc[0, "sim_drift"] == 0:
            df.loc[0, "p"] = 0.5
        else:
            df.loc[0, "p"] = (np.exp(-2 * z * df.loc[0, "sim_drift"]) - 1) / (
                    np.exp(-2 * df.loc[0, "sim_drift"]) - 1
            )
        df.loc[0, "response"] = np.random.binomial(1, df.loc[0, "p"], 1)
        if df.loc[0, "response"] == 1.0:
            df.loc[0, "feedback"] = df.loc[0, "rew_up"]
            if df.loc[0, "feedback"] > df.loc[0, "q_up"]:
                alfa = pos_alfa
            else:
                alfa = alpha
        else:
            df.loc[0, "feedback"] = df.loc[0, "rew_low"]
            if df.loc[0, "feedback"] > df.loc[0, "q_low"]:
                alfa = pos_alfa
            else:
                alfa = alpha

        for i in range(1, n):
            df.loc[i, "trial"] = i + 1
            df.loc[i, "q_up"] = (
                                        df.loc[i - 1, "q_up"] * (1 - df.loc[i - 1, "response"])
                                ) + (
                                        (df.loc[i - 1, "response"])
                                        * (
                                                df.loc[i - 1, "q_up"]
                                                + (alfa * (df.loc[i - 1, "rew_up"] - df.loc[i - 1, "q_up"]))
                                        )
                                )
            df.loc[i, "q_low"] = (
                                         df.loc[i - 1, "q_low"] * (df.loc[i - 1, "response"])
                                 ) + (
                                         (1 - df.loc[i - 1, "response"])
                                         * (
                                                 df.loc[i - 1, "q_low"]
                                                 + (alfa * (df.loc[i - 1, "rew_low"] - df.loc[i - 1, "q_low"]))
                                         )
                                 )
            df.loc[i, "sim_drift"] = (df.loc[i, "q_up"] - df.loc[i, "q_low"]) * (scaler)
            if 0.01 > df.loc[i, "sim_drift"] > -0.01:
                df.loc[i, "p"] = 0.5
            else:
                df.loc[i, "p"] = (np.exp(-2 * z * df.loc[i, "sim_drift"]) - 1) / (
                        np.exp(-2 * df.loc[i, "sim_drift"]) - 1
                )
            df.loc[i, "response"] = np.random.binomial(1, df.loc[i, "p"], 1)
            if df.loc[i, "response"] == 1.0:
                df.loc[i, "feedback"] = df.loc[i, "rew_up"]
                if df.loc[i, "feedback"] > df.loc[i, "q_up"]:
                    alfa = pos_alfa
                else:
                    alfa = alpha
            else:
                df.loc[i, "feedback"] = df.loc[i, "rew_low"]
                if df.loc[i, "feedback"] > df.loc[i, "q_low"]:
                    alfa = pos_alfa
                else:
                    alfa = alpha

        all_data.append(df)
    all_data = pd.concat(all_data, axis=0)
    all_data = all_data[
        [
            "q_up",
            "q_low",
            "p",
            "sim_drift",
            "response",
            "feedback",
            "subj_idx",
            "split_by",
            "trial",
        ]
    ]

    return all_data


# function that takes the data as input to simulate the same trials that the subject received
# the only difference from the simulation fit is that you update q-values not on the simulated choices but on the observed. but you still use the simulated rt and choices
# to look at ability to recreate choice patterns.
def gen_rand_rlddm_onestep_data(
        a, t, scaler, alpha, data, z=0.5, pos_alpha=float("nan")
):
    asub = a
    tsub = t
    df = data.reset_index()
    n = df.shape[0]
    df["sim_drift"] = 0
    df["sim_response"] = 0
    df["sim_rt"] = 0
    df["q_up"] = df["q_init"]
    df["q_low"] = df["q_init"]
    df["rew_up"] = df["feedback"]
    df["rew_low"] = df["feedback"]
    if np.isnan(pos_alpha):
        pos_alfa = alpha
    else:
        pos_alfa = pos_alpha
    sdata, params = hddm.generate.gen_rand_data(
        {"a": asub, "t": tsub, "v": df.loc[0, "sim_drift"], "z": z}, subjs=1, size=1
    )
    df.loc[0, "sim_response"] = sdata.response[0]
    if df.response[0] == 1:
        if df.loc[0, "feedback"] > df.loc[0, "q_up"]:
            alfa = pos_alfa
        else:
            alfa = alpha
    else:
        if df.loc[0, "feedback"] > df.loc[0, "q_low"]:
            alfa = pos_alfa
        else:
            alfa = alpha
    df.loc[0, "sim_rt"] = sdata.rt[0]

    for i in range(1, n):
        df.loc[i, "trial"] = i + 1
        df.loc[i, "q_up"] = (
                                    df.loc[i - 1, "q_up"] * (1 - df.loc[i - 1, "response"])
                            ) + (
                                    (df.loc[i - 1, "response"])
                                    * (
                                            df.loc[i - 1, "q_up"]
                                            + (alfa * (df.loc[i - 1, "rew_up"] - df.loc[i - 1, "q_up"]))
                                    )
                            )
        df.loc[i, "q_low"] = (df.loc[i - 1, "q_low"] * (df.loc[i - 1, "response"])) + (
                (1 - df.loc[i - 1, "response"])
                * (
                        df.loc[i - 1, "q_low"]
                        + (alfa * (df.loc[i - 1, "rew_low"] - df.loc[i - 1, "q_low"]))
                )
        )
        df.loc[i, "sim_drift"] = (df.loc[i, "q_up"] - df.loc[i, "q_low"]) * (scaler)
        sdata, params = hddm.generate.gen_rand_data(
            {"a": asub, "t": tsub, "v": df.loc[i, "sim_drift"], "z": z}, subjs=1, size=1
        )
        df.loc[i, "sim_response"] = sdata.response[0]
        df.loc[i, "sim_rt"] = sdata.rt[0]
        if df.response[i] == 1.0:
            if df.loc[i, "feedback"] > df.loc[i, "q_up"]:
                alfa = pos_alfa
            else:
                alfa = alpha
        else:
            if df.loc[i, "feedback"] > df.loc[i, "q_low"]:
                alfa = pos_alfa
            else:
                alfa = alpha
    return df


def add_outliers(data, n_fast, n_slow, seed=None):
    """Add outliers to data, outliers are distrbuted randomly across conditions.

    :Arguments:
         data: pd.DataFrame
            Reaction time and choice data
         n_fast: float
            Probability of fast outliers
         n_slow: float
            Probability of slow outliers
         seed: int <default=None>
            Seed for random number generation
    """
    data = pd.DataFrame(data)
    n_outliers = n_fast + n_slow
    if n_outliers == 0:
        return data

    if seed is not None:
        np.random.seed(seed)

    # init outliers DataFrame
    idx = np.random.permutation(len(data))[:n_outliers]
    outliers = data.iloc[idx, :].copy()

    # fast outliers
    outliers.loc[:, "rt"].iloc[:n_fast] = (
            np.random.rand(n_fast) * (min(abs(data["rt"])) - 0.1001) + 0.1001
    )

    # slow outliers
    outliers.loc[:, "rt"].iloc[n_fast:] = np.random.rand(n_slow) * 2 + max(
        abs(data["rt"])
    )
    outliers["response"] = np.random.randint(0, 2, n_outliers)

    # combine data with outliers
    data = pd.concat((data, outliers), ignore_index=True)
    return data
