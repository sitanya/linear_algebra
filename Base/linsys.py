# coding=utf-8
import traceback
from decimal import Decimal, getcontext

from copy import deepcopy

from Base.matrix import matrix as ma
from Vector import Vector
from plane import Plane
import numpy

getcontext().prec = 30


class LinearSystem(object):
    ALL_PLANES_MUST_BE_IN_SAME_DIM_MSG = 'All planes in the system should live in the same dimension'
    NO_SOLUTIONS_MSG = 'No solutions'

    INF_SOLUTIONS_MSG = 'Infinitely many solutions'

    def __init__(self, planes):
        try:
            d = planes[0].dimension
            for p in planes:
                assert p.dimension == d

            self.planes = planes
            self.dimension = d

        except AssertionError:
            raise Exception(self.ALL_PLANES_MUST_BE_IN_SAME_DIM_MSG)

    def swap_rows(self, row1, row2):
        cache = self[row1]
        self[row1] = self[row2]
        self[row2] = cache
        return self

    def multiply_coefficient_and_row(self, coefficient, row):
        self[row] = Plane(normal_vector=self[row].normal_vector.times_scaler(coefficient),
                          constant_term=coefficient * self[row].constant_term)
        return self

    def add_multiple_times_row_to_row(self, coefficient, row_to_add, row_to_be_added_to):
        self[row_to_be_added_to] = Plane(normal_vector=self[row_to_add].normal_vector.times_scaler(coefficient).plus(
            self[row_to_be_added_to].normal_vector),
            constant_term=coefficient * self[row_to_add].constant_term + self[
                row_to_be_added_to].constant_term)
        return self

    def indices_of_first_nonzero_terms_in_each_row(self):
        num_equations = len(self)

        indices = [-1] * num_equations

        for i, p in enumerate(self.planes):
            try:
                indices[i] = p.first_nonzero_index(p.normal_vector)
            except Exception as e:
                if str(e) == Plane.NO_NONZERO_ELTS_FOUND_MSG:
                    continue
                else:
                    raise 'traceback.format_exc():\n%s' % traceback.format_exc()

        return indices

    def __len__(self):
        return len(self.planes)

    def __getitem__(self, i):
        return self.planes[i]

    def __setitem__(self, i, x):
        try:
            assert x.dimension == self.dimension
            self.planes[i] = x

        except AssertionError:
            raise Exception(self.ALL_PLANES_MUST_BE_IN_SAME_DIM_MSG)

    def __str__(self):
        ret = 'Linear System:\n'
        temp = ['Equation {}: {}'.format(i + 1, p) for i, p in enumerate(self.planes)]
        ret += '\n'.join(temp)
        return ret

    def compute_triangular_form(self):
        system = deepcopy(self)
        num_equations = len(system)
        # 方程组中方程个数
        num_variables = system.dimension
        # 系数个数

        j = 0

        for i in range(num_equations):
            while j < num_variables:
                c = MyDecimal(system[i].normal_vector[j])
                if c.is_near_zero():
                    swap_succeeded = system.swap_with_row_below_for_nozero_coefficient_if_able(i, j)
                    if not swap_succeeded:
                        j += 1
                        continue
                system.clear_coefficients_below(i, j)
                j += 1
                break

        return system

    def swap_with_row_below_for_nozero_coefficient_if_able(self, row, col):
        num_equations = len(self)
        for k in range(row + 1, num_equations):
            coefficient = MyDecimal(self[k].normal_vector[col])
            if not coefficient.is_near_zero():
                self.swap_rows(row, k)
                return True
        return False

    def clear_coefficients_below(self, row, col):
        num_equations = len(self)
        beta = MyDecimal(self[row].normal_vector[col])
        for k in range(row + 1, num_equations):
            n = self[k].normal_vector
            gamma = n[col]
            alpha = -Decimal(gamma) / beta
            self.add_multiple_times_row_to_row(alpha, row, k)

    def compute_rref(self):
        tf = self.compute_triangular_form()
        num_equations = len(tf)
        pivot_indices = tf.indices_of_first_nonzero_terms_in_each_row()

        for i in range(num_equations)[::-1]:
            j = pivot_indices[i]
            if j < 0:
                continue
            tf.scale_row_to_make_coefficient_equal_one(i, j)
            tf.clear_coefficients_above(i, j)

        return tf

    def scale_row_to_make_coefficient_equal_one(self, row, col):
        n = self[row].normal_vector
        beta = Decimal('1.0') / Decimal(n[col])
        self.multiply_coefficient_and_row(beta, row)

    def clear_coefficients_above(self, row, col):
        for k in range(row)[::-1]:
            n = self[k].normal_vector
            alpha = -Decimal(n[col])
            self.add_multiple_times_row_to_row(alpha, row, k)

    def compute_solution(self):

        # return self.do_gaussian_elimination_and_extract_solution()
        return self.do_gaussian_elimination_and_parametrize_solution()

    def do_gaussian_elimination_and_extract_solution(self):
        rref = self.compute_rref()

        rref.raise_exception_if_contradictory_equation()
        rref.raise_exception_if_too_few_pivots()

        num_variables = rref.dimension

        solution_coordinates = [rref.planes[i].constant_term for i in range(num_variables)]
        return Vector(solution_coordinates)

    def do_gaussian_elimination_and_parametrize_solution(self):
        rref = self.compute_rref()

        rref.raise_exception_if_contradictory_equation()

        direction_vectors = rref.extract_direction_vectors_for_parametrization()
        basepoint = rref.extract_base_point_for_paramerization()
        # return Parametrization(basepoint,direction_vectors)

    def extract_direction_vectors_for_parametrization(self):
        num_variables = self.dimension
        pivot_indices = self.indices_of_first_nonzero_terms_in_each_row()
        free_variable_indices = set(range(num_variables)) - set(pivot_indices)

        direction_vectors = []
        for free_var in free_variable_indices:
            vector_coords = [0] * num_variables
            vector_coords[free_var] = 1
            for i, p in enumerate(self.planes):
                pivot_var = pivot_indices[i]
                if pivot_var < 0:
                    break
                vector_coords[pivot_var] = -p.normal_vector[free_var]
            direction_vectors.append(Vector(vector_coords))
        return direction_vectors

    def extract_base_point_for_paramerization(self):
        num_variables = self.dimension
        pivot_indices = self.indices_of_first_nonzero_terms_in_each_row()

        basepoint_coords = [0] * num_variables

        for i, p in enumerate(self.planes):
            pivot_var = pivot_indices[i]
            if pivot_var < 0:
                break
            basepoint_coords[pivot_var] = -p.constant_term

        return Vector(basepoint_coords)

    def raise_exception_if_contradictory_equation(self):
        for p in self.planes:
            try:
                p.first_nonzero_index(p.normal_vector)
            except Exception as e:
                if str(e) == 'No nonzero elements found':

                    constant_term = MyDecimal(p.constant_term)
                    if not constant_term.is_near_zero():
                        raise Exception(self.NO_SOLUTIONS_MSG)

    def raise_exception_if_too_few_pivots(self):
        pivot_indices = self.indices_of_first_nonzero_terms_in_each_row()
        num_pivots = sum([1 if index >= 0 else 0 for index in pivot_indices])

        num_variables = self.dimension

        if num_pivots < num_variables:
            raise Exception(self.INF_SOLUTIONS_MSG)

    @staticmethod
    def augmentMatrix(A, b):
        A_and_b_MUST_BE_HIVE_SAME_ROW = 'A and b 必须有相同行数'
        A_copy = deepcopy(A)
        augmentMatrix_list = []
        try:
            if A.__len__() != b.__len__():
                raise Exception
            for v, r in zip(A_copy, b):
                v.append(r[0])
                augmentMatrix_list.append(v)
            return augmentMatrix_list
        except Exception:
            raise Exception(A_and_b_MUST_BE_HIVE_SAME_ROW)

    @staticmethod
    def swapRows(M, r1, r2):
        cache = M[r1]
        M[r1] = M[r2]
        M[r2] = cache
        return M

    @staticmethod
    def scaleRow(M, r, scale):
        try:
            if scale == 0:
                raise ValueError(1)
            for col_num in range(0, M[r].__len__()):
                M[r][col_num] = M[r][col_num] * scale
            return M
        except ValueError as e:
            raise e

    @staticmethod
    def addScaledRow(M, r1, r2, scale):
        try:
            if scale == 0:
                raise ValueError(1)
            for col_num in range(0, M[r1].__len__()):
                M[r1][col_num] = M[r1][col_num] + scale * M[r2][col_num]
            return M
        except ValueError as e:
            raise e

    def matxRound(matx, decPts=4):
        for col in range(len(matx)):
            for row in range(len(matx[0])):
                matx[col][row] = round(matx[col][row], decPts)

    """ Gaussian Jordan 方法求解 Ax = b.
        参数
            A: 方阵 
            b: 列向量
            decPts: 四舍五入位数，默认为4
            epsilon: 判读是否为0的阈值，默认 1.0e-16

        返回列向量 x 使得 Ax = b 
        返回None，如果 A，b 高度不同
        返回None，如果 A 为奇异矩阵
    """

    @staticmethod
    def gj_Solve(A, b, epsilon=1.0e-16, decPts=4):
        if A.__len__() != b.__len__():
            return None
        m = LinearSystem.augmentMatrix(A, b)
        (eqns, colrange, augCol) = (len(A), len(A), len(m[0]))

        for col in range(0, colrange):
            bigrow = col
            for row in range(col + 1, colrange):
                if abs(m[row][col]) > abs(m[bigrow][col]):
                    bigrow = row
                    (m[col], m[bigrow]) = (m[bigrow], m[col])
        print "原" + str(numpy.array(m))
        # 排序

        try:
            for rrcol in range(0, colrange):
                for rr in range(rrcol + 1, eqns):
                    if m[rrcol][rrcol] != 0.0:
                        cc = -(float(m[rr][rrcol]) / float(m[rrcol][rrcol]))
                        for j in range(augCol):
                            m[rr][j] = m[rr][j] + cc * m[rrcol][j]
                    else:
                        cache = m[rrcol]
                        m[rrcol] = m[colrange]
                        m[colrange] = cache
                        cc = -(float(m[rr][rrcol]) / float(m[rrcol][rrcol]))
                        for j in range(augCol):
                            m[rr][j] = m[rr][j] + cc * m[rrcol][j]

        except Exception as e:
            print m[rrcol][rrcol]
            print numpy.array(m)
            print rrcol
        # 化简

        for rb in reversed(range(eqns)):
            if (m[rb][rb] == 0):
                if m[rb][augCol - 1] == 0:
                    continue
                else:
                    return None
            else:
                # you must loop back across to catch under-determined systems
                for backCol in reversed(range(rb, augCol)):
                    m[rb][backCol] = float(m[rb][backCol]) / float(m[rb][rb])
                # knock-up (cancel the above to eliminate the knowns)
                # again, we must loop to catch under-determined systems
                if not (rb == 0):
                    for kup in reversed(range(rb)):
                        for kleft in reversed(range(rb, augCol)):
                            kk = -float(m[kup][rb]) / float(m[rb][rb])
                            m[kup][kleft] += kk * float(m[rb][kleft])

        ma.matxRound(m, decPts)
        print "现" + str(numpy.array(m))

        for row in range(0, colrange):
            b[row] = [m[row][augCol - 1]]
        return b


class MyDecimal(Decimal):
    def is_near_zero(self, eps=1e-10):
        return abs(self) < eps


if __name__ == '__main__':
    A = [[3, 1, -1, 0]
        , [0, -6, 6, 7]
        , [-3, -6, 6, 2]
        , [1, 5, 3, -4]]
    b=[[2],[0],[1],[3]]

x = LinearSystem.gj_Solve(A, b, epsilon=1.0e-8)
