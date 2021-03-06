# ==================================================================================================
# Copyright 2011 Twitter, Inc.
# --------------------------------------------------------------------------------------------------
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this work except in compliance with the License.
# You may obtain a copy of the License in the LICENSE file, or at:
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==================================================================================================

__author__ = 'Mark C. Chu-Carroll'

import os
from collections import defaultdict
from zipfile import ZipFile

from twitter.common.java.class_file import ClassFile
from twitter.pants.targets.jar_dependency import JarDependency
from twitter.pants.targets.jvm_target import JvmTarget
from twitter.pants.tasks import TaskError


class JvmDependencyCache(object):
  """
  Class which computes and stores information about the compilation dependencies
  of targets for jvm-based languages.

  The behavior of this is determined by flags set in the compilation task's context.
  The flags (set by command-line options) are:
  - check_missing_deps: the master flag, which determines whether the dependency checks should
     be run at all.
  - check_intransitive_deps: a flag which determines whether or not to generate errors about
    intransitive dependency errors, where a target has a dependency on another target which
    it doesn't declare, but which is part of its transitive dependency graph. If this is set
    to "none", intransitive errors won't be reported. If "warn", then it will print warning
    messages, but will not cause the build to fail, and will not populate build products with the errors.
    If "error", then the messages will be printed, build products populated, and the build will fail.
  - check_unnecessary_deps: if set to True, then warning messages will be printed about dependencies
    that are declared, but not actually required.
  """

  @staticmethod
  def init_product_requirements(task):
    """
    Set the compilation product requirements that are needed for dependency analysis.

    Parameters:
      task: the task whose products should be set.
    """
    task._computed_jar_products = False
    task.context.products.require('classes')
    task.context.products.require('jar_dependencies',
              predicate = lambda x: JvmDependencyCache._requires_jardeps(task, x))

  @classmethod
  def setup_parser(cls, option_group, args, mkflag):
    """
    Set up command-line options for dependency checking.
    Any jvm compilation task that wants to use dependency analysis can call this from
    its setup_parser method to add the appropriate options for dependency testing.

    See scala_compile.py for an example.
    """
    option_group.add_option(mkflag("check-missing-deps"), mkflag("check-missing-deps", negate=True),
                            dest="scala_check_missing_deps",
                            action="callback", callback=mkflag.set_bool,
                            default=False,
                            help="[%default] Check for undeclared dependencies in scala code")

    # This flag should eventually be removed once code is in compliance.
    option_group.add_option(mkflag("check-missing-intransitive-deps"),
                            type="choice",
                            action='store',
                            dest='scala_check_intransitive_deps',
                            choices=['none', 'warn', 'error'],
                            default='none',
                            help="[%default] Enable errors for undeclared deps that don't cause compilation" \
                                  "errors, because the dependencies are provided transitively.")
    option_group.add_option(mkflag("check-unnecessary-deps"),
                            mkflag("check-unnecessary-deps", negate=True),
                            dest='scala_check_unnecessary_deps',
                            action="callback", callback=mkflag.set_bool,
                            default=False,
                            help="[%default] Enable warnings for declared dependencies that are not needed.")


  @staticmethod
  def _requires_jardeps(task, target):
    """
    Hack to make sure that the ivy task is not invoked more than once per compilation target.
    """
    if not task._computed_jar_products and isinstance(target, JvmTarget):
      task._computed_jar_products = True
      return True
    else:
      return False


  def __init__(self, compile_task, targets):
    """
    Parameters:
      compile_task: the compilation task which is producing the build products that
        we'll use to perform the analysis. Flag settings are also retrieved from the
        task context.
      targets: the set of targets to analyze. These should all be target types that
         inherit from jvm_target, and contain source files that will be compiled into
          jvm class files.
    """
    self.check_missing_deps = compile_task.context.options.scala_check_missing_deps
    self.check_intransitive_deps = compile_task.context.options.scala_check_intransitive_deps
    self.check_unnecessary_deps = compile_task.context.options.scala_check_unnecessary_deps
    self.task = compile_task
    self.targets = targets

    # class_deps_by_target contains the computed mappings from each target to
    # the set of classes it depends on.
    self.class_deps_by_target = defaultdict(set)

    # targets_by_class contains the computed mapping from a classfile generated
    # by compilation to the target whose compilation generated that class.
    self.targets_by_class = defaultdict(set)

    # pdeps_by_source contains the computed mapping from each source file
    # to the mappings from source file to a list of classes that we know they
    # depend on, because they're referenced in a class file generated by the source.
    self.deps_by_source = defaultdict(set)

    # mapping from a target to the jars it contains.
    self.jars_by_target = defaultdict(set)

    # mapping from class in a jar to the jardep target whose ivy artifacts include
    # the jar containing the class.
    # This is distinct from the other targets_by_class map,
    # because jar_dependencies aren't really targets.
    # They're a duck-typed retrofit that only partially works as a part of the
    # dependency graph - you can't walk them as part of the dependencies walk,
    # because they don't support being walked.
    self.jar_targets_by_class = defaultdict(set)

    # The result of the analysis: a computed map from each jvm target to the set of targets
    # that it depends on.
    self.computed_deps = None
    # Computed map from each jvm target to the set of jar targets that it includes
    self.computed_jar_deps = None

  def _get_jardep_dependencies(self, target):
    """
    Walks the dependency graph for a target, getting the transitive closure of
    its set of declared jar dependencies.
    """
    result = []
    target.walk(lambda t: self._walk_jardeps(t, result))
    return set(result)

  def _walk_jardeps(self, target, result):
    """
    A dependency walker for extracting jar dependencies from the dependency graph
    of targets in this compilation task.
    """
    if isinstance(target, JarDependency):
      result.append(target)
    if isinstance(target, JvmTarget):
      result.extend(target.jar_dependencies)

  def _compute_jar_contents(self):
    """
    Compute the information needed by deps analysis for the set of classes that come from
    jars in jar_dependency targets. This is messier that it should be, because of
    the strange way that jar_dependency targets are treated by pants.
    """
    # Get a list of all of the jar dependencies declared by the build targets.
    found_jar_deps = set()
    for jt in self.targets:
      jars = self._get_jardep_dependencies(jt)
      found_jar_deps = found_jar_deps.union(jars)
    jardeps_by_id = {}
    for jardep in found_jar_deps:
      jardeps_by_id[(jardep.org, jardep.name)] = jardep

    # Get the jar products. This is, unfortunately, a mess.
    # Assumes that the jar_dependency products are in the compile task.
    jar_products = self.task.context.products.get('jar_dependencies')

    # In the jar products, pants just throws a ton of stuff into the build
    # products. For each jar, they do the mappings:
    #   (org, confdir) -> jarfiles
    #   (org, name), confdir -> jarfiles
    #   (target, confdir) -> jarfiles
    #   (target, conf), confdir -> file
    #   (org, name, conf), confdir -> file
    for target_key, product in jar_products.itermappings():
      if isinstance(target_key, tuple):
        if target_key in jardeps_by_id:
          target = jardeps_by_id[target_key]
          jars_for_target = set([])
          for dir in jar_products.by_target[target_key]:
            for j in jar_products.by_target[target_key][dir]:
              jars_for_target.add(os.path.join(dir, j))
          self.jars_by_target[target] = jars_for_target
    for target in self.jars_by_target:
      for jar in self.jars_by_target[target]:
        jarfile = ZipFile(jar)
        for f in jarfile.filelist:
          if f.filename.endswith(".class"):
            self.jar_targets_by_class[f.filename].add(target)

  def _compute_source_deps(self):
    """
    Compute the set of dependencies actually used by the source files in the targets
    for the compilation task being analyzed.
    """
    # Get the class products from the compiler. This provides us with all the info we
    # need about what source file/target produces what class.
    class_products = self.task.context.products.get('classes')
    for target in self.targets:
      # for each target, compute a mapping from classes that the target generates to the target
      # this mapping is self.targets_by_class
      if target not in class_products.by_target:
        # If the target isn't in the products map, that means that it had no products - which
        # only happens if the target has no source files. This occurs when a target is created
        # as a placeholder.
        continue

      for outdir in class_products.by_target[target]:
        for cl in class_products.by_target[target][outdir]:
          self.targets_by_class[cl].add(target)

      # For each source in the current target, compute a mapping from source files to the classes that they
      # really depend on. (Done by parsing class files.)

      for source in target.sources:
        # we can get the set of classes from a source file by going into the same class_products object
        source_file_deps = set()
        class_files = set()
        for dir in class_products.by_target[source]:
          class_files |= set([ ( clfile, dir) for clfile in class_products.by_target[source][dir] ])

        # for each class file, get the set of referenced classes - these
        # are the classes that it depends on.
        for (cname, cdir) in class_files:
          cf = ClassFile.from_file(os.path.join(cdir, cname), False)
          dep_set = cf.get_external_class_references()
          dep_classfiles = [ "%s.class" % s for s in dep_set ]
          source_file_deps = source_file_deps.union(dep_classfiles)

        self.deps_by_source[source] = source_file_deps
        # add data from these classes to the target data in the map.
        self.class_deps_by_target[target].update(source_file_deps)

  def get_compilation_dependencies(self):
    """
    Computes a map from the source files in a target to class files that the source file
    depends on.

    Parameters:
      targets: a list of the targets from the current compile run whose
         dependencies should be analyzed.
    Returns: a target-to-target mapping from targets to targets that they depend on.
       If this was already computed, return the already computed result.
    """

    if self.computed_deps is not None:
      return (self.computed_deps, self.computed_jar_deps)

    self._compute_source_deps()
    self._compute_jar_contents()

    # Now, we have a map from target to the classes they depend on,
    # and a map from classes to the targets that provide them.
    # combining the two, we can get a map from target to targets that it really depends on.

    self.computed_deps = defaultdict(set)
    self.computed_jar_deps = defaultdict(set)
    for target in self.class_deps_by_target:
      target_dep_classes = self.class_deps_by_target[target]
      for cl in target_dep_classes:
        if cl in self.targets_by_class:
          self.computed_deps[target] = self.computed_deps[target].union(self.targets_by_class[cl])
        elif cl in self.jar_targets_by_class:
          self.computed_jar_deps[target] = self.computed_jar_deps[target].union(self.jar_targets_by_class[cl])
    return (self.computed_deps, self.computed_jar_deps)

  def get_dependency_blame(self, from_target, to_target):
    """
    Figures out why target A depends on target B according the the dependency analysis.
    Generates a tuple which can be used to generate a message like:
     "*from_target* depends on *to_target* because *from_target*'s source file X
      depends on *to_target*'s class Y."
     Returns: a pair of (source, class) where:
       source is the name of a source file in "from" that depends on something
          in "to".
       class is the name of the class that source1 depends on.
       If no dependency data could be found to support the dependency,
       returns (None, None)
    """
    # iterate over the sources in the from target.
    for source in from_target.sources:
      # for each class that the source depends on:
      for cl in self.deps_by_source[source]:
        # if that's in the target, then call it the culprit.
        if cl in self.targets_by_class and to_target in self.targets_by_class[cl]:
          return (source, cl)
    return (None, None)

  def check_undeclared_dependencies(self):
    """
    Performs the undeclared dependencies/overdeclared dependencies checks,
    generating warnings/error messages and (depending on flag settings),
    setting build products for the detected errors.
    """
    if not self.check_missing_deps:
        return
    (deps_by_target, jar_deps_by_target) = self.get_compilation_dependencies()
    found_missing_deps = False
    for target in deps_by_target:
      computed_deps = deps_by_target[target]
      computed_jar_deps = jar_deps_by_target[target]

      # Make copies of the computed deps. Then we'll walk the declared deps,
      # removing everything that was declared; what's left are the undeclared deps.
      undeclared_deps = computed_deps.copy()
      undeclared_jar_deps = computed_jar_deps.copy()
      target.walk(lambda target: self._dependency_walk_work(undeclared_deps, undeclared_jar_deps, target))
      # The immediate (intransitive) missing deps are everything that isn't declared as a dep
      # of this target.
      immediate_missing_deps = computed_deps.difference(target.dependencies).difference([target])
      if len(undeclared_deps) > 0:
        found_missing_deps = True
        genmap = self.task.context.products.get('missing_deps')
        genmap.add(target, self.task.context._buildroot, [x.derived_from.address.reference() for x in undeclared_deps])
        for dep_target in undeclared_deps:
          print ("Error: target %s has undeclared compilation dependency on %s," %
                 (target.address, dep_target.derived_from.address.reference()))
          print ("       because source file %s depends on class %s" %
                 self.get_dependency_blame(target, dep_target))
          immediate_missing_deps.discard(dep_target)
      #if len(jar_deps) > 0:
      #  found_missing_deps = True
      #  for jd in jar_deps:
      #    print ("Error: target %s needs to depend on jar_dependency %s.%s" %
      #          (target.address, jd.org, jd.name))
      if self.check_intransitive_deps != "none":
        if len(immediate_missing_deps) > 0:
          genmap = self.task.context.products.get('missing_deps')
          if self.check_intransitive_deps == "error":
            found_missing_deps = True
            genmap.add(target, self.context._buildroot,
                       [x.derived_from.address.reference() for x in immediate_missing_deps])
          for missing in immediate_missing_deps:
            print ("Error: target %s depends on %s which is only declared transitively" % (target, missing))
      if self.check_unnecessary_deps:
        overdeps = (target.declared_dependencies).difference(computed_deps)
        if len(overdeps) > 0:
          for d in overdeps:
            print ("Warning: target %s declares un-needed dependency on: %s" % (target, d))

    if found_missing_deps:
      raise TaskError('Missing dependencies detected.')


  def _dependency_walk_work(self, deps, jar_deps, target):
    if target in deps:
      deps.remove(target)
    if isinstance(target, JvmTarget):
      for jar_dep in target.dependencies:
        if jar_dep in jar_deps:
          jar_deps.remove(jar_dep)
