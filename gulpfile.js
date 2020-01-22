// GULPFILE
// - - - - - - - - - - - - - - -
// This file processes all of the assets in the "src" folder
// and outputs the finished files in the "dist" folder.

// 1. LIBRARIES
// - - - - - - - - - - - - - - -
const { src, pipe, dest, series, parallel, watch } = require('gulp');

const plugins = {};
plugins.addSrc = require('gulp-add-src');
plugins.babel = require('gulp-babel');
plugins.cleanCSS = require('gulp-clean-css');
plugins.cssUrlAdjuster = require('gulp-css-url-adjuster');
plugins.concat = require('gulp-concat');
plugins.cssUrlAdjuster = require('gulp-css-url-adjuster');
plugins.prettyerror = require('gulp-prettyerror');
plugins.rollup = require('gulp-better-rollup')
plugins.sass = require('gulp-sass');

// 2. CONFIGURATION
// - - - - - - - - - - - - - - -
const paths = {
  src: 'assets/',
  dist: 'static/',
  templates: 'templates/vendor/govuk/',
  govuk_frontend: 'node_modules/govuk-frontend/govuk/'
};

let staticPathMatcher = new RegExp('^\/assets\/');

// 3. TASKS
// - - - - - - - - - - - - - - -

// Move GOV.UK template resources

const copy = {
  govuk_frontend: {
    template: () => {
      return src(paths.govuk_frontend + 'template.njk')
        .pipe(dest(paths.templates));
    },
    components: () => {
      return src(paths.govuk_frontend + 'components/**/*')
        .pipe(dest(paths.templates + 'components/'));
    },
    fonts: () => {
      return src(paths.govuk_frontend + 'assets/fonts/**/*')
        .pipe(dest(paths.dist + 'fonts/'));
    },
    images: () => {
      return src(paths.govuk_frontend + 'assets/images/**/*')
        .pipe(dest(paths.dist + 'images/'));
    }
  }
};


const sass = () => {
  return src([
      paths.src + 'main.scss'
  ])
    .pipe(plugins.prettyerror())
    .pipe(plugins.sass({
      outputStyle: 'nested',
      includePaths: [
        paths.govuk_frontend
      ]
    }))
    .pipe(plugins.cssUrlAdjuster({
      replace: [staticPathMatcher, '/static/']
    }))
    .pipe(plugins.concat(
      'all.css'
    ))
    .pipe(dest(paths.dist))
};


// Copy images
const images = () => {
  return src([
      paths.govuk_frontend + 'assets/images/**/*'
    ])
    .pipe(dest(paths.dist + 'images/'))
};


const watchFiles = {
  sass: (cb) => {
    watch([paths.src], sass);
    cb();
  },
  self: (cb) => {
    watch(['gulpfile.js'], defaultTask);
    cb();
  }
};


// Default: compile everything
const defaultTask = parallel(
  parallel(
    copy.govuk_frontend.template,
    copy.govuk_frontend.components,
    copy.govuk_frontend.fonts,
    copy.govuk_frontend.images
  ),
  series(
    sass
  )
);


// Watch for changes and re-run tasks
const watchForChanges = parallel(
  watchFiles.sass,
  watchFiles.self
);


exports.default = defaultTask;

// Optional: recompile on changes
exports.watch = series(defaultTask, watchForChanges);
