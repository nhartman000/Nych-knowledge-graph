from typing import List
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa

from nych.symbols import Symbol


class NychVisualizer:
    def __init__(self):
        self.fig = plt.figure(figsize=(8, 8))
        self.ax = self.fig.add_subplot(111, projection="3d")

        self.ax.set_xlabel("X (time)")
        self.ax.set_ylabel("Y (region)")
        self.ax.set_zlabel("Z (volume)")

        self.ax.set_title("NYCH Locality Explorer")

    def _extract_xyz(self, address):
        """
        Address is a tuple:
        (x=time, y=region, z=volume, d4=context)
        """
        if address is None:
            return (0.0, 0.0, 0.0)

        try:
            return address[0], address[1], address[2]
        except Exception:
            return (0.0, 0.0, 0.0)

    def plot_symbols(self, symbols: List[Symbol]):
        xs, ys, zs = [], [], []

        for sym in symbols:
            x, y, z = self._extract_xyz(sym.address)
            xs.append(x)
            ys.append(y)
            zs.append(z)

            self.ax.text(
                x,
                y,
                z,
                sym.glyph,
                fontsize=12,
                ha="center",
                va="center",
            )

        self.ax.scatter(xs, ys, zs, s=40, depthshade=True)

    def save(self, path: str):
        plt.tight_layout()
        plt.savefig(path)
        plt.close(self.fig)

    def show(self):
        plt.show()
