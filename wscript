#! /usr/bin/env python
# encoding: utf-8

from waflib import Scripting, Logs, Options, Errors
from waflib.Errors import WafError
import sys

def try_git_version():
    import os
    import sys

    version = None
    try:
        #version = os.popen('git describe --always --dirty --long').read().strip().strip("v")
        version = os.popen('./build-aux/git-version-gen .tarball-version').read()
    except Exception as e:
        print e
    return version

# the following two variables are used by the target "waf dist"
APPNAME="hackterm"
VERSION = try_git_version()
out = 'build'

def options(opt):
        opt.load('compiler_cxx compiler_c gnu_dirs waf_unit_test')
        opt.load('coverage daemon', tooldir=['./waftools/'])
        opt.add_option('--onlytests', action='store_true',
		       default=True, help='Exec unit tests only', dest='only_tests')

        opt.add_option('--lcov-report',
                        help=('Generate a code coverage report '
                                '(use this option at build time, not in configure)'),
                        action="store_true", default=False,
                        dest='lcov_report')

def configure(conf):
        # load these things from waf
        conf.load('compiler_cxx compiler_c gnu_dirs waf_unit_test')
        conf.load('coverage daemon', tooldir=['./waftools/'])

	conf.check_cfg(package='sdl2', uselib_store='SDL2',
		       args=['--cflags', '--libs'], atleast_version='2.0')
	conf.check_cfg(package='libssh2', uselib_store='LIBSSH2',
		       args=['--cflags', '--libs'], atleast_version='1.4.3')
	conf.check_cfg(package='libpng12', uselib_store='LIBPNG',
		       args=['--cflags', '--libs'], atleast_version='1.2')

	conf.check(lib='z', uselib_store='Z')
	conf.check(lib='m', uselib_store='M')
        conf.check(header_name='pthread.h')
        conf.check(lib='pthread', uselib_store='PTHREAD')
        conf.check(lib='util', uselib_store='UTIL')
        conf.check(lib='crypto', uselib_store='CRYPTO')

        conf.define('VERSION', VERSION)
        conf.define('PACKAGE_STRING', APPNAME)
        conf.define('BINDIR', conf.env['BINDIR'])

        conf.env.append_unique('LDFLAGS', '-static')
        conf.env.append_unique('CFLAGS', '-g')
	conf.env.append_unique('CFLAGS', '-std=gnu99')
        conf.env.append_unique('CXXFLAGS', '-g')

        if sys.platform == 'linux2':
	    conf.define('LINUX_BUILD', '1')
	    conf.define('LOCAL_ENABLE', '1')

	if sys.platform == 'darwin':
	    conf.define('OSX_BUILD', '1')
	    conf.define('LOCAL_ENABLE', '1')
	
        conf.write_config_header('config.h')

def build(bld):
    if sys.platform == 'linux2':
	    bld(includes = 'linux',
		export_includes = 'linux',
		name = 'linux_includes')

    bld.add_post_fun(gtest_results)
    #bld.options.all_tests = True
    #from waflib.Tools import waf_unit_test
    #bld.add_post_fun(waf_unit_test.summary)

    if Options.options.lcov_report:
        lcov_report(bld)

    bld(features = 'cstlib c',
	target = 'libutf8proc',
	includes = 'utf8proc',
	export_includes = 'utf8proc',
	vnum = '0.0.0',
	source = """
	    utf8proc/utf8proc.c
	""")


    bld(features = 'cstlib c',
	target = 'libvterm',
	includes = 'libvterm/include libvterm/src',
	export_includes = 'libvterm/include libvterm/src',
	vnum = '0.0.0',
	source = """
	    libvterm/src/parser.c
	    libvterm/src/screen.c
	    libvterm/src/input.c
	    libvterm/src/vterm.c
	    libvterm/src/unicode.c
	    libvterm/src/state.c
	    libvterm/src/encoding.c
	    libvterm/src/pen.c
	""")

    bld(features='cxx',
	target='unifont_conv',
	use='SDL2',
	source="""
	    unifont_conv.c
	    nunifont.c
	""")

    bld(features='cxx',
	target='hackterm',
	use='linux_includes SDL2 LIBSSH2 LIBPNG Z M PTHREAD CRYPTO UTIL libvterm libutf8proc',
	source="""
	    main.c
	    base64.c
	    inlinedata.c
	    local.c
	    ngui_button.c
	    ngui.c
	    ngui_info_prompt.c
	    ngui_stringselect.c
	    ngui_textbox.c
	    ngui_textlabel.c
	    nsdl.c
	    nunifont.c
	    regis.c
	    ssh.c
	""")

def dist(ctx):
        ctx.base_name = APPNAME + "_" + VERSION
        ctx.excl = ' **/.waf-1* **/*~ **/*.pyc **/*.swp **/.lock-w* **/.git build'
        ctx.algo = 'tar.bz2'

def gtest_results(bld):
    lst = getattr(bld, 'utest_results', [])
    if not lst:
        return
    for (f, code, out, err) in lst:
        # if not code:
        #     continue

        # uncomment if you want to see what's happening
        # print(str(out).encode('utf-8'))
        output = str(out).encode('utf-8').split('\n')
        for i, line in enumerate(output):
            if '[ RUN      ]' in line and code:
                i += 1
                if '    OK ]' in output[i]:
                    continue
                while not '[ ' in output[i]:
                    Logs.warn('%s' % output[i])
                    i += 1
            elif ' FAILED  ]' in line and code:
                Logs.error('%s' % line)
            elif ' PASSED  ]' in line:
                Logs.info('%s' % line)


def lcov_report(bld):
    import os
    import subprocess

    env = bld.env

    if not env['GCOV']:
        raise WafError("project not configured for code coverage;"
                       " reconfigure with --with-coverage")

    os.chdir(out)
    try:
        lcov_report_dir = 'lcov-report'
        create_dir_command = "rm -rf " + lcov_report_dir
        create_dir_command += " && mkdir " + lcov_report_dir + ";"

        if subprocess.Popen(create_dir_command, shell=True).wait():
            raise SystemExit(1)

        info_file = os.path.join(lcov_report_dir, 'report.info')
        lcov_command = "lcov -c -d . -o " + info_file
        lcov_command += " -b " + os.getcwd()
        if subprocess.Popen(lcov_command, shell=True).wait():
            raise SystemExit(1)

        genhtml_command = "genhtml --no-branch-coverage -o " + lcov_report_dir
        genhtml_command += " " + info_file
        if subprocess.Popen(genhtml_command, shell=True).wait():
            raise SystemExit(1)
    finally:
        os.chdir("..")
