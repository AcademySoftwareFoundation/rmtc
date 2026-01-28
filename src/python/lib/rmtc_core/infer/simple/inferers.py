# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.artifacts import Dataset
from rmtc.infer import Inferer
from rmtc.system import Context


class DatasetInferer(Inferer):
    """
    Simple dataset to dataset inference
    """

    def __init__(
        self,
        model=None,
        weights=None,
        inputs=None,
        outputs=None,
        context=Context.GPU,
        postprocess=None,
    ):
        """Initialize FolderInferer with model, paths, and file handlers."""
        super(DatasetInferer, self).__init__(
            model=model,
            weights=weights,
            context=context,
            postprocess=postprocess,
        )
        self.add_property("inputs", Dataset, inputs, member=False)
        self.add_property("outputs", Dataset, outputs, member=False)

    def __call__(self):

        # run
        inference = self.run(self.inputs, self.outputs)

        # return
        return inference
