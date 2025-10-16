# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

# ----------------------------------------------------------------------------
# If you submit this package back to Spack as a pull request,
# please first remove this boilerplate and all FIXME comments.
#
# This is a template package file for Spack.  We've put "FIXME"
# next to all the things you'll want to change. Once you've handled
# them, you can save this file and test your package like this:
#
#     spack install environ
#
# You can edit this file again by typing:
#
#     spack edit environ
#
# See the Spack documentation for more information on packaging.
# ----------------------------------------------------------------------------


from spack.package import *


class Environ(Package):
    """Environ is a computational library aimed at introducing environment effects to atomistic first-principles
    simulations, in particular for applications in surface science and materials design. """

    homepage = "https://www.quantum-environ.org"
    git = "https://github.com/environ-developers/Environ/releases/download/v3.0/Environ.tar.gz"
    maintainers("eric-read","olivieroandreussi", "JakobFilser")
    # See https://spdx.org/licenses/ for a list. Upon manually verifying
    # the license, set checked_by to your Github username.
    license("GPL-2.0-only", checked_by="eric-read")

    version("develop", branch="master")
    version("3.1", sha256="a143a028e243c2bdb0779e61478029d5f0c5ddfee07d7beda06200d677401893")
    version("3.0", sha256="95476a056801d7c4be6329e4593b2fceeedc773170c5e20aa707d7d58f8b8932")

    variant("openmp", default=False, description="Enables OpenMP support")
    # Need OpenMP threaded FFTW and BLAS libraries when configured
    # with OpenMP support
    with when("+openmp"):
        depends_on("fftw+openmp", when="^[virtuals=fftw-api] fftw")
        depends_on("amdfftw+openmp", when="^[virtuals=fftw-api] amdfftw")
        depends_on("openblas threads=openmp", when="^[virtuals=blas] openblas")
        depends_on("amdblis threads=openmp", when="^[virtuals=blas] amdblis")
        depends_on("intel-mkl threads=openmp", when="^[virtuals=blas] intel-mkl")
        depends_on("armpl-gcc threads=openmp", when="^[virtuals=blas] armpl-gcc")
        depends_on("acfl threads=openmp", when="^[virtuals=blas] acfl")
    
    variant("mpi", default=True, description="Builds with mpi support")
    with when("+mpi"):
        depends_on("mpi")

    depends_on("blas")
    depends_on("fftw-api@3")
    depends_on("m4", type="build")
    depends_on("c", type="build")
    depends_on("fortran", type="build")
    depends_on("gmake", type="build")
    
    requires("^[virtuals=fftw-api] intel-oneapi-mkl", when="^[virtuals=lapack] intel-oneapi-mkl")
    requires("^[virtuals=lapack] intel-oneapi-mkl", when="^[virtuals=fftw-api] intel-oneapi-mkl")

    # CONFLICTS SECTION
    # Omitted for now due to concretizer bug
    # MKL with 64-bit integers not supported.
    # conflicts(
    #     '^mkl+ilp64',
    #     msg='Environ does not support MKL 64-bit integer variant'
    # )
    # depends_on("foo")
    conflicts(
        "%aocc", msg="Internal compiler error with aocc"
    )

    def configure_args(self):
        # FIXME: Add arguments other than --prefix
        # FIXME: If not needed delete this function
        args = []
        return args

class GenericBuilder(GenericBuilder):
    def install(self, pkg, spec, prefix):
        prefix_path = prefix.bin if "@:3.0" in spec else prefix
        options = ["-prefix={0}".format(prefix_path)]
        
        # This additional flag is needed anytime the target architecture
        # does not match the host architecture, which results in a binary that
        # configure cannot execute on the login node. This is how we detect
        # cross compilation: If the platform is NOT either Linux or Darwin
        # and the target=backend, that we are in the cross-compile scenario
        # scenario. This should cover Cray, BG/Q, and other custom platforms.
        # The other option is to list out all the platform where you would be
        # cross compiling explicitly.
        if not (spec.satisfies("platform=linux") or spec.satisfies("platform=darwin")):
            if spec.satisfies("target=backend"):
                options.append("--host")

                   # QE autoconf compiler variables has some limitations:
        # 1. There is no explicit MPICC variable so we must re-purpose
        #    CC for the case of MPI.
        # 2. F90 variable is set to be consistent with MPIF90 wrapper
        # 3. If an absolute path for F90 is set, the build system breaks.
        #
        # Thus, due to 2. and 3. the F90 variable is not explictly set
        # because it would be mostly pointless and could lead to erroneous
        # behaviour.
        if "+mpi" in spec:
            mpi = spec["mpi"]
            options.append("--enable-parallel=yes")
            options.append("MPIF90={0}".format(mpi.mpifc))
            options.append("CC={0}".format(mpi.mpicc))
        else:
            options.append("--enable-parallel=no")
            options.append("CC={0}".format(env["SPACK_CC"]))

        options.append("F77={0}".format(env["SPACK_F77"]))
        options.append("F90={0}".format(env["SPACK_FC"]))

        if "+openmp" in spec:
            options.append("--enable-openmp")

        # QE external BLAS, FFT, SCALAPACK detection is a bit tricky.
        # More predictable to pass in the correct link line to QE.
        # If external detection of BLAS, LAPACK and FFT fails, QE
        # is supposed to revert to internal versions of these libraries
        # instead -- but more likely it will pickup versions of these
        # libraries found in its the system path, e.g. Red Hat or
        # Ubuntu's FFTW3 package.

        # FFT
        # FFT detection gets derailed if you pass into the CPPFLAGS, instead
        # you need to pass it in the FFTW_INCLUDE and FFT_LIBS directory.
        # QE supports an internal FFTW2, but only an external FFTW3 interface.

        is_using_intel_libraries = spec["lapack"].name in INTEL_MATH_LIBRARIES
        if is_using_intel_libraries:
            # A seperate FFT library is not needed when linking against MKL
            options.append("FFTW_INCLUDE={0}".format(join_path(env["MKLROOT"], "include/fftw")))
        if "^fftw@3:" in spec:
            fftw_prefix = spec["fftw"].prefix
            options.append("FFTW_INCLUDE={0}".format(fftw_prefix.include))
            if "+openmp" in spec:
                fftw_ld_flags = spec["fftw:openmp"].libs.ld_flags
            else:
                fftw_ld_flags = spec["fftw"].libs.ld_flags
            options.append("FFT_LIBS={0}".format(fftw_ld_flags))

        if "^amdfftw" in spec:
            fftw_prefix = spec["amdfftw"].prefix
            options.append("FFTW_INCLUDE={0}".format(fftw_prefix.include))
            if "+openmp" in spec:
                fftw_ld_flags = spec["amdfftw:openmp"].libs.ld_flags
            else:
                fftw_ld_flags = spec["amdfftw"].libs.ld_flags
            options.append("FFT_LIBS={0}".format(fftw_ld_flags))

        # External BLAS and LAPACK requires the correct link line into
        # BLAS_LIBS, do no use LAPACK_LIBS as the autoconf scripts indicate
        # that this variable is largely ignored/obsolete.

        # For many Spack packages, lapack.libs = blas.libs, hence it will
        # appear twice in in link line but this is harmless
        lapack_blas = spec["lapack"].libs + spec["blas"].libs

        if not is_using_intel_libraries:
            options.append("BLAS_LIBS={0}".format(lapack_blas.ld_flags))
        
        configure(*options)

        parallel_build_on = True

        make("compile", parallel=parallel_build_on)
