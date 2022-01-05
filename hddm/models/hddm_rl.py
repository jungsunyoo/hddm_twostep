"""
"""

from copy import copy
import numpy as np
import pymc
import wfpt

from kabuki.hierarchical import Knode
from kabuki.utils import stochastic_from_dist
from hddm.models import HDDM
from wfpt import wiener_like_rlddm, wiener_like_rlddm_2step, wiener_like_rlddm_2step_reg


class HDDMrl(HDDM):
    """HDDM model that can be used for two-armed bandit tasks."""

    # just 2-stage rlddm

    def __init__(self, *args, **kwargs):
        self.non_centered = kwargs.pop("non_centered", False)
        self.dual = kwargs.pop("dual", False)
        self.alpha = kwargs.pop("alpha", True)
        # self.w = kwargs.pop("w", True) # added for two-step task
        self.gamma = kwargs.pop("gamma", True) # added for two-step task
        self.lambda_ = kwargs.pop("lambda_", True) # added for two-step task
        self.wfpt_rl_class = WienerRL

        super(HDDMrl, self).__init__(*args, **kwargs)


    # 2-stage rlddm regression

    # def __init__(self, *args, **kwargs):
    #     self.non_centered = kwargs.pop("non_centered", False)
    #     self.dual = kwargs.pop("dual", False)
    #     self.alpha = kwargs.pop("alpha", True)
    #     self.gamma = kwargs.pop("gamma", True) # added for two-step task
    #     self.lambda_ = kwargs.pop("lambda_", True) # added for two-step task

    #     # self.v0 = kwargs.pop("v0", True)
    #     # self.v1 = kwargs.pop("v1", True)
    #     # self.v2 = kwargs.pop("v2", True)


    #     # self.z0 = kwargs.pop("z0", True)
    #     # self.z1 = kwargs.pop("z1", True)
    #     # self.z2 = kwargs.pop("z2", True)


    #     self.wfpt_rl_class = WienerRL

    #     super(HDDMrl, self).__init__(*args, **kwargs)

    def _create_stochastic_knodes(self, include):
        knodes = super(HDDMrl, self)._create_stochastic_knodes(include)
        if self.non_centered:
            print("setting learning rate parameter(s) to be non-centered")
            if self.alpha:
                knodes.update(
                    self._create_family_normal_non_centered(
                        "alpha",
                        value=0,
                        g_mu=0.2,
                        g_tau=3 ** -2,
                        std_lower=1e-10,
                        std_upper=10,
                        std_value=0.1,
                    )
                )
            if self.dual:
                knodes.update(
                    self._create_family_normal_non_centered(
                        "pos_alpha",
                        value=0,
                        g_mu=0.2,
                        g_tau=3 ** -2,
                        std_lower=1e-10,
                        std_upper=10,
                        std_value=0.1,
                    )
                )
            # if self.w:
            #     knodes.update(
            #         self._create_family_normal_non_centered(
            #             "w",
            #             value=0,
            #             g_mu=0.2,
            #             g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            #     ) 
            if self.gamma:
                knodes.update(
                    self._create_family_normal_non_centered(
                        "gamma",
                        value=0,
                        g_mu=0.2,
                        g_tau=3 ** -2,
                        std_lower=1e-10,
                        std_upper=10,
                        std_value=0.1,
                    )
                ) 
            if self.lambda_:
                knodes.update(
                    self._create_family_normal_non_centered(
                        "lambda_",
                        value=0,
                        g_mu=0.2,
                        g_tau=3 ** -2,
                        std_lower=1e-10,
                        std_upper=10,
                        std_value=0.1,
                    )
                )

            # if self.v0:
            #     knodes.update(
            #         self._create_family_normal_non_centered(
            #             "v0",
            #             value=0,
            #             g_tau=50 ** -2, 
            #             # std_std=10,
            #             # g_mu=0.2,
            #             # g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            #     )

            # if self.v1:
            #     knodes.update(
            #         self._create_family_normal_non_centered(
            #             "v1",
            #             value=0,
            #             g_tau=50 ** -2, 
            #             # std_std=10,
            #             # g_mu=0.2,
            #             # g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            # )
            # if self.v2:
            #     knodes.update(
            #         self._create_family_normal_non_centered(
            #             "v2",
            #             value=0,
            #             g_tau=50 ** -2, 
            #             # std_std=10,
            #             # g_mu=0.2,
            #             # g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            # )




        else:
            if self.alpha:
                knodes.update(
                    self._create_family_normal(
                        "alpha",
                        value=0,
                        g_mu=0.2,
                        g_tau=3 ** -2,
                        std_lower=1e-10,
                        std_upper=10,
                        std_value=0.1,
                    )
                )
            if self.dual:
                knodes.update(
                    self._create_family_normal(
                        "pos_alpha",
                        value=0,
                        g_mu=0.2,
                        g_tau=3 ** -2,
                        std_lower=1e-10,
                        std_upper=10,
                        std_value=0.1,
                    )
                )
            # if self.w:
            #     knodes.update(
            #         self._create_family_normal(
            #             "w",
            #             value=0,
            #             g_mu=0.2,
            #             g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            #     )   
            if self.gamma:
                knodes.update(
                    self._create_family_normal(
                        "gamma",
                        value=0,
                        g_mu=0.2,
                        g_tau=3 ** -2,
                        std_lower=1e-10,
                        std_upper=10,
                        std_value=0.1,
                    )
                )
            if self.lambda_:
                knodes.update(
                    self._create_family_normal(
                        "lambda_",
                        value=0,
                        g_mu=0.2,
                        g_tau=3 ** -2,
                        std_lower=1e-10,
                        std_upper=10,
                        std_value=0.1,
                    )
                )


        # if "v2" in include:
        #     knodes.update(
        #         self._create_family_normal_normal_hnormal(
        #             "v2", value=2, g_mu=2, g_tau=3 ** -2, std_std=2
        #         )
        #     )

# "v0", value=0, g_tau=50 ** -2, std_std=10

            # if self.v0:
            #     knodes.update(
            #         self._create_family_normal(
            #             "v0",
            #             value=0,
            #             g_tau=50 ** -2, 
            #             # std_std=10,
            #             # g_mu=0.2,
            #             # g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            #     )

            # if self.v1:
            #     knodes.update(
            #         self._create_family_normal(
            #             "v1",
            #             value=0,
            #             g_tau=50 ** -2, 
            #             # std_std=10,
            #             # g_mu=0.2,
            #             # g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            # )
            # if self.v2:
            #     knodes.update(
            #         self._create_family_normal(
            #             "v2",
            #             value=0,
            #             g_tau=50 ** -2, 
            #             # std_std=10,
            #             # g_mu=0.2,
            #             # g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            # )




            # )

            # if self.z0:
            #     knodes.update(
            #         self._create_family_normal(
            #             "z0",
            #             value=0,
            #             g_mu=0.2,
            #             g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            #     )

            # if self.z1:
            #     knodes.update(
            #         self._create_family_normal(
            #             "z1",
            #             value=0,
            #             g_mu=0.2,
            #             g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )
            #     )
            # if self.z2:
            #     knodes.update(
            #         self._create_family_normal(
            #             "z2",
            #             value=0,
            #             g_mu=0.2,
            #             g_tau=3 ** -2,
            #             std_lower=1e-10,
            #             std_upper=10,
            #             std_value=0.1,
            #         )





            # )
# )
        return knodes

    def _create_wfpt_parents_dict(self, knodes):
        wfpt_parents = super(HDDMrl, self)._create_wfpt_parents_dict(knodes)
        wfpt_parents["alpha"] = knodes["alpha_bottom"]
        wfpt_parents["pos_alpha"] = knodes["pos_alpha_bottom"] if self.dual else 100.00


        # wfpt_parents["w"] = knodes["w_bottom"]
        wfpt_parents["gamma"] = knodes["gamma_bottom"]
        wfpt_parents["lambda_"] = knodes["lambda__bottom"]

        # wfpt_parents["v0"] = knodes["v0_bottom"]
        # wfpt_parents["v1"] = knodes["v1_bottom"]
        # wfpt_parents["v2"] = knodes["v2_bottom"]


        return wfpt_parents

    def _create_wfpt_knode(self, knodes):
        wfpt_parents = self._create_wfpt_parents_dict(knodes)
        return Knode(
            self.wfpt_rl_class,
            "wfpt",
            observed=True,
            # col_name=["split_by", "feedback", "response1", "response2", "rt1", "rt2",  "q_init", "state1", "state2", ],
            col_name=["split_by", "feedback", "response1", "response2", "rt1", "rt2",  "q_init", "state1", "state2", "isleft1", "isleft2"],
            **wfpt_parents
        )


def wienerRL_like(x, v, alpha, pos_alpha, sv, a, z, sz, t, st, p_outlier=0):

    wiener_params = {
        "err": 1e-4,
        "n_st": 2,
        "n_sz": 2,
        "use_adaptive": 1,
        "simps_err": 1e-3,
        "w_outlier": 0.1,
    }
    wp = wiener_params
    response = x["response"].values.astype(int)
    q = x["q_init"].iloc[0]
    feedback = x["feedback"].values.astype(float)
    split_by = x["split_by"].values.astype(int)
    return wiener_like_rlddm(
        x["rt"].values,
        response,
        feedback,
        split_by,
        q,
        alpha,
        pos_alpha,
        v,
        sv,
        a,
        z,
        sz,
        t,
        st,
        p_outlier=p_outlier,
        **wp
    )

# def wienerRL_like_2step(x, v, alpha, pos_alpha, w, gamma, lambda_, sv, a, z, sz, t, st, p_outlier=0):
def wienerRL_like_2step(x, v, alpha, pos_alpha, gamma, lambda_, sv, a, z, sz, t, st, p_outlier=0):
    wiener_params = {
        "err": 1e-4,
        "n_st": 2,
        "n_sz": 2,
        "use_adaptive": 1,
        "simps_err": 1e-3,
        "w_outlier": 0.1,
    }
    wp = wiener_params
    response1 = x["response1"].values.astype(int)
    response2 = x["response2"].values.astype(int)
    state1 = x["state1"].values.astype(int)
    state2 = x["state2"].values.astype(int)

    isleft1 = x["isleft1"].values.astype(int)
    isleft2 = x["isleft2"].values.astype(int)


    q = x["q_init"].iloc[0]
    feedback = x["feedback"].values.astype(float)
    split_by = x["split_by"].values.astype(int)


    # YJS added for two-step tasks on 2021-12-05
    # nstates = x["nstates"].values.astype(int)
    nstates = max(x["state2"].values.astype(int)) + 1


    return wiener_like_rlddm_2step(
        x["rt1"].values,
        x["rt2"].values,
        state1,
        state2,
        response1,
        response2,
        feedback,
        split_by,
        q,
        alpha,
        pos_alpha, 
        # w, # added for two-step task
        gamma, # added for two-step task 
        lambda_, # added for two-step task 
        v,
        sv,
        a,
        z,
        sz,
        t,
        nstates,
        st,
        p_outlier=p_outlier,
        **wp
    )
# # def wienerRL_like_2step_reg(x, v, alpha, pos_alpha, w, gamma, lambda_, sv, a, z, sz, t, st, p_outlier=0):
# # def wienerRL_like_2step_reg(x, v, v0, v1, v2, alpha, pos_alpha, gamma, lambda_, sv, a, z, sz, t, st, p_outlier=0):
# def wienerRL_like_2step_reg(x, v, alpha, pos_alpha, gamma, lambda_, sv, a, z, sz, t, st, p_outlier=0):
#     wiener_params = {
#         "err": 1e-4,
#         "n_st": 2,
#         "n_sz": 2,
#         "use_adaptive": 1,
#         "simps_err": 1e-3,
#         "w_outlier": 0.1,
#     }
#     wp = wiener_params
#     response1 = x["response1"].values.astype(int)
#     response2 = x["response2"].values.astype(int)
#     state1 = x["state1"].values.astype(int)
#     state2 = x["state2"].values.astype(int)

#     isleft1 = x["isleft1"].values.astype(int)
#     isleft2 = x["isleft2"].values.astype(int)


#     q = x["q_init"].iloc[0]
#     feedback = x["feedback"].values.astype(float)
#     split_by = x["split_by"].values.astype(int)


#     # YJS added for two-step tasks on 2021-12-05
#     # nstates = x["nstates"].values.astype(int)
#     nstates = max(x["state2"].values.astype(int)) + 1


#     return wiener_like_rlddm_2step_reg(
#         x["rt1"].values,
#         x["rt2"].values,
#         state1,
#         state2,
#         response1,
#         response2,
#         feedback,
#         split_by,
#         q,
#         alpha,
#         pos_alpha, 
#         # w, # added for two-step task
#         gamma, # added for two-step task 
#         lambda_, # added for two-step task 
#         v,
#         sv,
#         a,
#         z,
#         sz,
#         t,
#         nstates,
#         st,
#         p_outlier=p_outlier,
#         **wp
#     )




def wienerRL_like_2step_reg(x, v, alpha, pos_alpha, gamma, lambda_, sv, a, z, sz, t, st, p_outlier=0):

    wiener_params = {
        "err": 1e-4,
        "n_st": 2,
        "n_sz": 2,
        "use_adaptive": 1,
        "simps_err": 1e-3,
        "w_outlier": 0.1,
    }
    wp = wiener_params
    response1 = x["response1"].values.astype(int)
    response2 = x["response2"].values.astype(int)
    state1 = x["state1"].values.astype(int)
    state2 = x["state2"].values.astype(int)

    isleft1 = x["isleft1"].values.astype(int)
    isleft2 = x["isleft2"].values.astype(int)


    q = x["q_init"].iloc[0]
    feedback = x["feedback"].values.astype(float)
    split_by = x["split_by"].values.astype(int)


    # YJS added for two-step tasks on 2021-12-05
    # nstates = x["nstates"].values.astype(int)
    nstates = max(x["state2"].values.astype(int)) + 1


    return wiener_like_rlddm_2step_reg(
        x["rt1"].values,
        x["rt2"].values,
        state1,
        state2,
        response1,
        response2,
        feedback,
        split_by,
        q,
        alpha,
        pos_alpha, 
        # w, # added for two-step task
        gamma, # added for two-step task 
        lambda_, # added for two-step task 
        v,
        sv,
        a,
        z,
        sz,
        t,
        nstates,
        st,
        p_outlier=p_outlier,
        **wp
    )
# WienerRL = stochastic_from_dist("wienerRL", wienerRL_like)
WienerRL = stochastic_from_dist("wienerRL_2step", wienerRL_like_2step)
# WienerRL = stochastic_from_dist("wienerRL_2step_reg", wienerRL_like_2step_reg)

